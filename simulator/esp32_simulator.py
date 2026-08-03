from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


LOGGER = logging.getLogger("esp32_simulator")


def create_payload(node_id: str) -> dict:
    return {
        "nodo_id": node_id,
        "timestamp_sensor": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "lecturas": {
            "temp": round(random.uniform(18.0, 29.0), 2),
            "hum": round(random.uniform(35.0, 75.0), 2),
            "co": round(random.uniform(1.0, 12.0), 2),
            "pm25": round(random.uniform(5.0, 45.0), 2),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simula las publicaciones MQTT de un ESP32."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Cantidad de mensajes; 0 mantiene el envío continuo.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("SIMULATOR_INTERVAL_SECONDS", "2")),
        help="Segundos entre publicaciones.",
    )
    parser.add_argument(
        "--node-id",
        default=os.getenv("ESP32_NODE_ID", "ESP32_01"),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    if args.count < 0:
        raise SystemExit("--count no puede ser negativo.")
    if args.interval < 0:
        raise SystemExit("--interval no puede ser negativo.")

    broker = os.getenv("MQTT_BROKER", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC_INPUT", "nodo/esp32/sensores")
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"simulator_{args.node_id}",
        protocol=mqtt.MQTTv311,
    )

    username = os.getenv("MQTT_USERNAME")
    if username:
        client.username_pw_set(username, os.getenv("MQTT_PASSWORD"))
    if os.getenv("MQTT_TLS", "false").lower() in {"1", "true", "yes"}:
        client.tls_set()

    LOGGER.info("Conectando a MQTT %s:%s.", broker, port)
    client.connect(broker, port, keepalive=60)
    client.loop_start()

    sent = 0
    try:
        while args.count == 0 or sent < args.count:
            payload = create_payload(args.node_id)
            info = client.publish(
                topic,
                json.dumps(payload),
                qos=1,
            )
            info.wait_for_publish()
            sent += 1
            LOGGER.info(
                "Publicación %s de %s en %s: %s",
                sent,
                args.count if args.count else "∞",
                topic,
                json.dumps(payload["lecturas"]),
            )
            if args.count == 0 or sent < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        LOGGER.info("Simulación detenida por el usuario.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()

