from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BROKER_PORT = 18883
API_PORT = 18000


def wait_for_port(host: str, port: int, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"El puerto {host}:{port} no respondió a tiempo.")


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_measurement(url: str, timeout: float = 15) -> dict:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return read_json(url)
        except (urllib.error.URLError, urllib.error.HTTPError) as error:
            last_error = error
            time.sleep(0.25)
    raise TimeoutError(
        f"No se recibió una medición en {url}. Último error: {last_error}"
    )


def start_process(
    command: list[str],
    env: dict[str, str],
    log_path: Path,
) -> tuple[subprocess.Popen, object]:
    log_handle = log_path.open("w", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=flags,
    )
    return process, log_handle


def show_logs(log_paths: list[Path]) -> None:
    for path in log_paths:
        print(f"\n--- {path.name} ---")
        if path.exists():
            print(path.read_text(encoding="utf-8", errors="replace"))


def main() -> int:
    processes: list[subprocess.Popen] = []
    handles: list[object] = []

    # Windows puede mantener un log recién cerrado bloqueado durante unos
    # milisegundos. La limpieza diferida no debe convertir una prueba exitosa
    # del flujo IoT en un falso negativo.
    with tempfile.TemporaryDirectory(
        prefix="iot_e2e_",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        temp_path = Path(temp_dir)
        logs = [
            temp_path / "broker.log",
            temp_path / "api.log",
            temp_path / "edge.log",
        ]
        env = os.environ.copy()
        env.update(
            {
                "MQTT_BROKER": "127.0.0.1",
                "MQTT_BROKER_BIND": "127.0.0.1",
                "MQTT_PORT": str(BROKER_PORT),
                "CONSOLIDATION_LIMIT": "5",
                "API_RETRY_COUNT": "2",
                "API_URL": f"http://127.0.0.1:{API_PORT}/mediciones",
                "DATABASE_PATH": str(temp_path / "mediciones.db"),
                "LOG_LEVEL": "INFO",
                "PYTHONUNBUFFERED": "1",
            }
        )

        try:
            broker, broker_log = start_process(
                [sys.executable, "-m", "broker.local_broker"],
                env,
                logs[0],
            )
            processes.append(broker)
            handles.append(broker_log)
            wait_for_port("127.0.0.1", BROKER_PORT)

            api, api_log = start_process(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(API_PORT),
                ],
                env,
                logs[1],
            )
            processes.append(api)
            handles.append(api_log)
            wait_for_port("127.0.0.1", API_PORT)

            health = read_json(f"http://127.0.0.1:{API_PORT}/health")
            if health.get("estado") != "ok":
                raise RuntimeError(f"Respuesta de salud inesperada: {health}")

            edge, edge_log = start_process(
                [sys.executable, "-m", "edge.edge_processor"],
                env,
                logs[2],
            )
            processes.append(edge)
            handles.append(edge_log)
            time.sleep(1)

            simulator = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "simulator.esp32_simulator",
                    "--count",
                    "5",
                    "--interval",
                    "0.1",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if simulator.returncode != 0:
                raise RuntimeError(
                    "El simulador falló:\n"
                    f"{simulator.stdout}\n{simulator.stderr}"
                )

            measurement = wait_for_measurement(
                f"http://127.0.0.1:{API_PORT}/mediciones/ultima"
            )
            if measurement["muestras_procesadas"] != 5:
                raise AssertionError(
                    "La API no recibió las cinco muestras consolidadas."
                )
            if measurement["nodo_origen"] != "ESP32_01":
                raise AssertionError("El nodo de origen no coincide.")

            print("PRUEBA E2E EXITOSA")
            print(
                "Simulador ESP32 -> MQTT -> Edge -> HTTP -> FastAPI -> SQLite"
            )
            print(json.dumps(measurement, indent=2, ensure_ascii=False))
            return 0
        except Exception as error:
            print(f"PRUEBA E2E FALLIDA: {error}")
            show_logs(logs)
            return 1
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
