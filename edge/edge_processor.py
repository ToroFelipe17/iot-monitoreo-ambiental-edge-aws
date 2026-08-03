from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real
from typing import Any

import httpx
import paho.mqtt.client as mqtt


LOGGER = logging.getLogger("edge_processor")
CAMPOS_REQUERIDOS = ("temp", "hum", "co", "pm25")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
    }


@dataclass(frozen=True)
class EdgeConfig:
    broker: str = os.getenv("MQTT_BROKER", "127.0.0.1")
    port: int = int(os.getenv("MQTT_PORT", "1883"))
    topic_input: str = os.getenv(
        "MQTT_TOPIC_INPUT", "nodo/esp32/sensores"
    )
    client_id: str = os.getenv(
        "MQTT_CLIENT_ID_EDGE", "Edge_Processor_Core"
    )
    username: str | None = os.getenv("MQTT_USERNAME") or None
    password: str | None = os.getenv("MQTT_PASSWORD") or None
    use_tls: bool = env_bool("MQTT_TLS")
    gateway_id: str = os.getenv(
        "EDGE_GATEWAY_ID", "GATEWAY_CURICO_01"
    )
    consolidation_limit: int = int(
        os.getenv("CONSOLIDATION_LIMIT", "30")
    )
    api_url: str = os.getenv(
        "API_URL", "http://127.0.0.1:8000/mediciones"
    )
    http_timeout: float = float(
        os.getenv("HTTP_TIMEOUT_SECONDS", "5")
    )
    api_retry_count: int = int(os.getenv("API_RETRY_COUNT", "3"))


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, Real) and not isinstance(valor, bool)


def validar_y_filtrar(datos: Any) -> bool:
    """
    Conserva la validación física del código original y agrega comprobación
    numérica para impedir errores de tipo o valores inválidos de CO.
    """
    if not isinstance(datos, dict):
        return False
    if not isinstance(datos.get("nodo_id"), str) or not datos["nodo_id"]:
        return False

    lecturas = datos.get("lecturas")
    if not isinstance(lecturas, dict):
        return False
    if not all(campo in lecturas for campo in CAMPOS_REQUERIDOS):
        return False
    if not all(_es_numero(lecturas[campo]) for campo in CAMPOS_REQUERIDOS):
        return False

    return (
        -15.0 <= float(lecturas["temp"]) <= 50.0
        and 0.0 <= float(lecturas["hum"]) <= 100.0
        and 0.0 <= float(lecturas["co"]) <= 1000.0
        and 0.0 <= float(lecturas["pm25"]) <= 1000.0
    )


def consolidar(
    nodo_id: str,
    lecturas: list[dict[str, float]],
    gateway_id: str,
) -> dict[str, Any]:
    total = len(lecturas)
    if total == 0:
        raise ValueError("No se puede consolidar un buffer vacío.")

    return {
        "edge_gateway_id": gateway_id,
        "nodo_origen": nodo_id,
        "timestamp_borde": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "muestras_procesadas": total,
        "datos_consolidados": {
            "temperatura_c": round(
                sum(item["temp"] for item in lecturas) / total, 2
            ),
            "humedad_relativa": round(
                sum(item["hum"] for item in lecturas) / total, 2
            ),
            "co_ppm": round(
                sum(item["co"] for item in lecturas) / total, 2
            ),
            "pm25_ugm3": round(
                sum(item["pm25"] for item in lecturas) / total, 2
            ),
        },
        "estado_nodo": "OPERACIONAL",
    }


class EdgeProcessor:
    def __init__(
        self,
        config: EdgeConfig,
        http_client: httpx.Client | None = None,
    ) -> None:
        if config.consolidation_limit < 1:
            raise ValueError("CONSOLIDATION_LIMIT debe ser mayor que cero.")
        if config.api_retry_count < 1:
            raise ValueError("API_RETRY_COUNT debe ser mayor que cero.")

        self.config = config
        self.buffers: dict[str, list[dict[str, float]]] = defaultdict(list)
        self.http_client = http_client or httpx.Client(
            timeout=config.http_timeout
        )
        self._owns_http_client = http_client is None

    def procesar_payload(self, payload: bytes | str) -> bool:
        try:
            raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            datos = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            LOGGER.warning("Dato descartado: JSON inválido (%s).", error)
            return False

        if not validar_y_filtrar(datos):
            LOGGER.warning(
                "Dato descartado: trama incompleta o fuera de rango."
            )
            return False

        nodo_id = datos["nodo_id"]
        lecturas = datos["lecturas"]
        self.buffers[nodo_id].append(
            {
                "temp": float(lecturas["temp"]),
                "hum": float(lecturas["hum"]),
                "co": float(lecturas["co"]),
                "pm25": float(lecturas["pm25"]),
            }
        )
        LOGGER.info(
            "Lectura válida de %s (%s/%s).",
            nodo_id,
            len(self.buffers[nodo_id]),
            self.config.consolidation_limit,
        )

        if len(self.buffers[nodo_id]) < self.config.consolidation_limit:
            return True

        paquete = consolidar(
            nodo_id,
            self.buffers[nodo_id],
            self.config.gateway_id,
        )
        if self.enviar_a_api(paquete):
            self.buffers[nodo_id].clear()
        return True

    def enviar_a_api(self, paquete: dict[str, Any]) -> bool:
        for intento in range(1, self.config.api_retry_count + 1):
            try:
                response = self.http_client.post(
                    self.config.api_url,
                    json=paquete,
                )
                response.raise_for_status()
                LOGGER.info(
                    "Paquete de %s persistido en la API (HTTP %s).",
                    paquete["nodo_origen"],
                    response.status_code,
                )
                return True
            except httpx.HTTPError as error:
                LOGGER.error(
                    "Fallo HTTP %s/%s hacia %s: %s",
                    intento,
                    self.config.api_retry_count,
                    self.config.api_url,
                    error,
                )
                if intento < self.config.api_retry_count:
                    time.sleep(min(2 ** (intento - 1), 4))
        LOGGER.error(
            "El paquete se conserva en memoria para reintentar con la "
            "próxima lectura."
        )
        return False

    def close(self) -> None:
        if self._owns_http_client:
            self.http_client.close()


def build_mqtt_client(
    processor: EdgeProcessor,
) -> mqtt.Client:
    config = processor.config
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=config.client_id,
        protocol=mqtt.MQTTv311,
    )

    if config.username:
        client.username_pw_set(config.username, config.password)
    if config.use_tls:
        client.tls_set()

    def on_connect(
        connected_client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code == 0:
            connected_client.subscribe(config.topic_input, qos=1)
            LOGGER.info(
                "Conectado a MQTT %s:%s; suscrito a %s.",
                config.broker,
                config.port,
                config.topic_input,
            )
        else:
            LOGGER.error("Conexión MQTT rechazada: %s.", reason_code)

    def on_message(
        _client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        processor.procesar_payload(message.payload)

    def on_disconnect(
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            LOGGER.warning(
                "Conexión MQTT interrumpida; se intentará reconectar: %s.",
                reason_code,
            )

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = EdgeConfig()
    processor = EdgeProcessor(config)
    client = build_mqtt_client(processor)

    LOGGER.info(
        "Iniciando edge: MQTT %s:%s -> HTTP %s; consolidación=%s.",
        config.broker,
        config.port,
        config.api_url,
        config.consolidation_limit,
    )
    try:
        client.connect(config.broker, config.port, keepalive=60)
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        LOGGER.info("Detención solicitada por el usuario.")
    finally:
        client.disconnect()
        processor.close()


if __name__ == "__main__":
    main()

