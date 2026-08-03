from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


PAYLOAD = {
    "edge_gateway_id": "GATEWAY_TEST",
    "nodo_origen": "ESP32_TEST",
    "timestamp_borde": "2026-07-27T16:00:00Z",
    "muestras_procesadas": 5,
    "datos_consolidados": {
        "temperatura_c": 22.5,
        "humedad_relativa": 51.2,
        "co_ppm": 4.1,
        "pm25_ugm3": 12.8,
    },
    "estado_nodo": "OPERACIONAL",
}


def test_api_guarda_y_recupera_medicion(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        response = client.post("/mediciones", json=PAYLOAD)
        assert response.status_code == 201
        assert response.json()["id"] == 1

        latest = client.get("/mediciones/ultima")
        assert latest.status_code == 200
        assert latest.json()["nodo_origen"] == "ESP32_TEST"

        listed = client.get("/mediciones?limit=10")
        assert listed.status_code == 200
        assert len(listed.json()) == 1


def test_api_rechaza_medicion_fuera_de_rango(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    invalid = {
        **PAYLOAD,
        "datos_consolidados": {
            **PAYLOAD["datos_consolidados"],
            "humedad_relativa": 150,
        },
    }
    with TestClient(app) as client:
        response = client.post("/mediciones", json=invalid)
        assert response.status_code == 422

