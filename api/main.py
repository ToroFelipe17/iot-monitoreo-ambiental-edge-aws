from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from api.database import (
    database_path,
    init_database,
    insert_measurement,
    latest_measurement,
    list_measurements,
)


class DatosConsolidados(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperatura_c: float = Field(ge=-15, le=50)
    humedad_relativa: float = Field(ge=0, le=100)
    co_ppm: float = Field(ge=0, le=1000)
    pm25_ugm3: float = Field(ge=0, le=1000)


class MedicionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_gateway_id: str = Field(min_length=1, max_length=80)
    nodo_origen: str = Field(min_length=1, max_length=80)
    timestamp_borde: datetime
    muestras_procesadas: int = Field(gt=0, le=10000)
    datos_consolidados: DatosConsolidados
    estado_nodo: str = Field(min_length=1, max_length=40)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="API de Monitoreo Ambiental IoT",
    description=(
        "Recibe mediciones consolidadas por el dispositivo de borde y las "
        "persiste localmente en SQLite."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["sistema"])
def root() -> dict[str, str]:
    return {
        "servicio": "API de Monitoreo Ambiental IoT",
        "documentacion": "/docs",
        "salud": "/health",
    }


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"estado": "ok", "base_datos": str(database_path())}


@app.post(
    "/mediciones",
    status_code=status.HTTP_201_CREATED,
    tags=["mediciones"],
)
def create_measurement(measurement: MedicionEntrada) -> dict:
    return insert_measurement(
        measurement.model_dump(mode="json")
    )


@app.get("/mediciones", tags=["mediciones"])
def get_measurements(
    limit: int = Query(default=20, ge=1, le=500),
) -> list[dict]:
    return list_measurements(limit)


@app.get("/mediciones/ultima", tags=["mediciones"])
def get_latest_measurement() -> dict:
    measurement = latest_measurement()
    if measurement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todavía no existen mediciones almacenadas.",
        )
    return measurement

