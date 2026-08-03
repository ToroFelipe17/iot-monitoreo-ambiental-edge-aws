import json

import httpx

from edge.edge_processor import EdgeConfig, EdgeProcessor, consolidar, validar_y_filtrar


VALID_PAYLOAD = {
    "nodo_id": "ESP32_01",
    "lecturas": {
        "temp": 22.0,
        "hum": 55.0,
        "co": 5.0,
        "pm25": 15.0,
    },
}


def test_validar_y_filtrar_acepta_trama_correcta():
    assert validar_y_filtrar(VALID_PAYLOAD)


def test_validar_y_filtrar_rechaza_campos_o_rangos_invalidos():
    assert not validar_y_filtrar({"nodo_id": "ESP32_01"})
    assert not validar_y_filtrar(
        {
            "nodo_id": "ESP32_01",
            "lecturas": {
                "temp": 100,
                "hum": 50,
                "co": 2,
                "pm25": 10,
            },
        }
    )
    assert not validar_y_filtrar(
        {
            "nodo_id": "ESP32_01",
            "lecturas": {
                "temp": "22",
                "hum": 50,
                "co": 2,
                "pm25": 10,
            },
        }
    )


def test_consolidar_calcula_promedios():
    paquete = consolidar(
        "ESP32_01",
        [
            {"temp": 20, "hum": 40, "co": 2, "pm25": 10},
            {"temp": 24, "hum": 60, "co": 4, "pm25": 20},
        ],
        "GATEWAY_TEST",
    )
    assert paquete["muestras_procesadas"] == 2
    assert paquete["datos_consolidados"] == {
        "temperatura_c": 22.0,
        "humedad_relativa": 50.0,
        "co_ppm": 3.0,
        "pm25_ugm3": 15.0,
    }


def test_processor_envia_y_limpia_buffer_despues_del_limite():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(201, json={"id": 1})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    processor = EdgeProcessor(
        EdgeConfig(consolidation_limit=2, api_retry_count=1),
        http_client=http_client,
    )

    assert processor.procesar_payload(json.dumps(VALID_PAYLOAD))
    assert processor.procesar_payload(json.dumps(VALID_PAYLOAD))
    assert len(requests) == 1
    assert requests[0]["muestras_procesadas"] == 2
    assert processor.buffers["ESP32_01"] == []

