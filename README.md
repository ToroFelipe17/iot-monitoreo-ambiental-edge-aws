# Sistema IoT de monitoreo ambiental con Edge y AWS

Implementación académica de un flujo IoT para monitorear variables ambientales y demostrar cómo se conectan un nodo ESP32, MQTT, procesamiento en el borde, una API FastAPI y almacenamiento SQLite.

## Problema

Un sistema de monitoreo ambiental necesita recibir mediciones desde distintos sectores, revisar su calidad y conservar resultados útiles para consulta. Enviar cada lectura directamente a la nube aumenta el tráfico y hace que el sistema dependa más de la conectividad.

La propuesta procesa primero las mediciones en un dispositivo edge. De esta forma, se validan los datos, se descartan valores fuera de rango y se consolidan varias lecturas antes de enviarlas a la API.

## Arquitectura

```text
Simulador ESP32 o ESP32 real
             |
             | MQTT
             v
       Broker MQTT local
             |
             v
       Edge en Python
   validación y promedios
             |
             | HTTP POST
             v
       API FastAPI
       local o AWS EC2
             |
             v
          SQLite
```

Flujo principal:

```text
Simulador ESP32 → MQTT → Edge Python → HTTP → FastAPI → AWS EC2 → SQLite
```

El broker y el procesamiento edge permanecen cerca del origen de los datos. La nube recibe únicamente paquetes validados y consolidados.

## Tecnologías

- Python 3.11 o posterior.
- MQTT mediante `paho-mqtt`.
- Broker MQTT local de desarrollo incluido en el proyecto.
- FastAPI y Uvicorn.
- SQLite para persistencia local.
- Pytest para pruebas.
- Ubuntu Server y `systemd` para un despliegue opcional en AWS EC2.
- PowerShell para la ejecución local en Windows.

## Estructura

```text
api/                       API FastAPI y persistencia SQLite
broker/                    Broker MQTT local para laboratorio
deploy/aws/                Servicio systemd y guía genérica de despliegue
docs/                      Trazabilidad y notas del proyecto
edge/                      Validación, filtrado y consolidación
simulator/                 Simulador del nodo ESP32
scripts/                   Instalación y prueba extremo a extremo
tests/                     Pruebas unitarias
data/.gitkeep              Directorio para la base generada localmente
.env.example               Variables de configuración de referencia
```

## Ejecución local en Windows

Requisitos: Windows 10/11, Python 3.11+, PowerShell y conexión a internet para instalar dependencias.

Abrir PowerShell en la carpeta del proyecto y ejecutar:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

La prueba automática levanta los componentes necesarios, publica cinco lecturas y comprueba que el resultado quede persistido:

```powershell
.\.venv\Scripts\python.exe .\scripts\e2e_test.py
```

Salida esperada:

```text
PRUEBA E2E EXITOSA
Simulador ESP32 -> MQTT -> Edge -> HTTP -> FastAPI -> SQLite
```

## Ejecución manual

En cuatro ventanas de PowerShell, dentro del proyecto:

```powershell
# Ventana 1: broker MQTT
.\.venv\Scripts\python.exe -m broker.local_broker
```

```powershell
# Ventana 2: API
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Ventana 3: edge
$env:CONSOLIDATION_LIMIT = "5"
.\.venv\Scripts\python.exe -m edge.edge_processor
```

```powershell
# Ventana 4: simulador ESP32
.\.venv\Scripts\python.exe -m simulator.esp32_simulator --count 5 --interval 0.5
```

Endpoints locales:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/mediciones`
- `http://127.0.0.1:8000/mediciones/ultima`

La base se crea en `data/mediciones.db` y está excluida del repositorio.

## Sustituir el simulador por un ESP32

El ESP32 debe publicar en el tópico `nodo/esp32/sensores` un JSON con esta estructura:

```json
{
  "nodo_id": "ESP32_01",
  "lecturas": {
    "temp": 23.4,
    "hum": 61.2,
    "co": 5.8,
    "pm25": 16.0
  }
}
```

El BME280 puede entregar temperatura y humedad. Las variables de CO y PM2.5 pueden provenir de los sensores correspondientes o simularse durante una prueba controlada, dejando esa diferencia explícita.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

La prueba E2E valida el recorrido completo entre el simulador, el broker, el edge, la API y SQLite. En la implementación original se comprobaron seis pruebas automatizadas, compilación correcta, dependencias sin conflictos y persistencia de cinco lecturas consolidadas.

## Despliegue documentado en AWS EC2

El despliegue opcional aloja FastAPI y SQLite en una instancia Linux. El broker MQTT y el edge pueden permanecer en la red local o en un gateway.

La guía completa está en [`deploy/aws/README.md`](deploy/aws/README.md). Usa siempre valores propios para usuario, región, DNS, IP y clave SSH. Nunca guardes una clave `.pem`, credenciales o una dirección pública real dentro del repositorio.

Recomendaciones mínimas para una demostración:

- Ubuntu Server LTS.
- Security group exclusivo.
- SSH (22) solo desde la IP del administrador.
- API (8000) solo desde la IP del edge y únicamente durante la prueba.
- No exponer MQTT (1883) a internet.
- Eliminar la instancia, volumen y recursos asociados al finalizar.

## Seguridad y limitaciones

Este proyecto es un prototipo académico. La versión demostrada utilizó restricciones de red, pero no debe considerarse lista para producción.

Antes de un uso real se debería agregar:

- TLS para MQTT y HTTP.
- Autenticación y autorización.
- Gestión de secretos fuera del repositorio.
- Validación y calibración formal de sensores.
- Reintentos, colas y respaldo ante pérdida de conectividad.
- Monitoreo y logs centralizados.
- Una base administrada si SQLite deja de ser suficiente.

También existe una diferencia entre el diseño completo y la demostración: para validar el flujo extremo a extremo se utilizó un simulador con el mismo contrato JSON esperado por el ESP32. Esto permitió probar la integración sin afirmar que todos los sensores físicos estaban conectados durante la demostración.

## Capturas sugeridas

Las capturas deben agregarse solo después de eliminar IP públicas, DNS, identificadores de instancia, número de cuenta, claves y datos personales.

- Terminal con `PRUEBA E2E EXITOSA`.
- Swagger `/docs` con los endpoints.
- Respuesta de `/mediciones/ultima` con una medición consolidada.
- Diagrama del flujo de arquitectura.

## Créditos y aportes

- **Felipe Toro:** integración del flujo, API FastAPI, despliegue y configuración AWS, pruebas extremo a extremo y documentación pública.
- **Sebastián Tancara:** selección de sensores, ESP32, captura de mediciones y contrato de datos.
- **Pedro González:** procesamiento en el dispositivo edge, validación, filtrado y consolidación de lecturas.

## Licencia

Este repositorio se publica bajo licencia MIT. La implementación se desarrolló con fines académicos y demostrativos.
