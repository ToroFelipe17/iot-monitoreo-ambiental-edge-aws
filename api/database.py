from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def database_path() -> Path:
    configured = Path(os.getenv("DATABASE_PATH", "data/mediciones.db"))
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return configured


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mediciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_gateway_id TEXT NOT NULL,
                nodo_origen TEXT NOT NULL,
                timestamp_borde TEXT NOT NULL,
                muestras_procesadas INTEGER NOT NULL CHECK (muestras_procesadas > 0),
                temperatura_c REAL NOT NULL,
                humedad_relativa REAL NOT NULL,
                co_ppm REAL NOT NULL,
                pm25_ugm3 REAL NOT NULL,
                estado_nodo TEXT NOT NULL,
                recibido_en TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
            )
            """
        )


def insert_measurement(payload: dict[str, Any]) -> dict[str, Any]:
    consolidated = payload["datos_consolidados"]
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO mediciones (
                edge_gateway_id,
                nodo_origen,
                timestamp_borde,
                muestras_procesadas,
                temperatura_c,
                humedad_relativa,
                co_ppm,
                pm25_ugm3,
                estado_nodo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["edge_gateway_id"],
                payload["nodo_origen"],
                payload["timestamp_borde"],
                payload["muestras_procesadas"],
                consolidated["temperatura_c"],
                consolidated["humedad_relativa"],
                consolidated["co_ppm"],
                consolidated["pm25_ugm3"],
                payload["estado_nodo"],
            ),
        )
        row = connection.execute(
            "SELECT * FROM mediciones WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return serialize_row(row)


def list_measurements(limit: int) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM mediciones ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [serialize_row(row) for row in rows]


def latest_measurement() -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM mediciones ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return serialize_row(row) if row else None


def serialize_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "edge_gateway_id": row["edge_gateway_id"],
        "nodo_origen": row["nodo_origen"],
        "timestamp_borde": row["timestamp_borde"],
        "muestras_procesadas": row["muestras_procesadas"],
        "datos_consolidados": {
            "temperatura_c": row["temperatura_c"],
            "humedad_relativa": row["humedad_relativa"],
            "co_ppm": row["co_ppm"],
            "pm25_ugm3": row["pm25_ugm3"],
        },
        "estado_nodo": row["estado_nodo"],
        "recibido_en": row["recibido_en"],
    }

