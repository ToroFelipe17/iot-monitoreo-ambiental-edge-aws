# Despliegue genérico en AWS EC2

Esta guía muestra cómo alojar la API FastAPI y SQLite en una instancia Linux. Reemplaza todos los marcadores por valores propios y revisa los costos y beneficios vigentes de tu cuenta antes de crear recursos.

## 1. Crear la instancia

- Ubuntu Server LTS.
- Tipo pequeño elegible para tu cuenta.
- Volumen raíz mínimo y eliminación al terminar.
- Security group exclusivo.

Reglas recomendadas para laboratorio:

- TCP 22 solo desde la IP pública del administrador.
- TCP 8000 solo desde la IP pública del edge, durante la demostración.
- No exponer MQTT 1883 a internet.
- No usar `0.0.0.0/0` para SSH ni para la API.

## 2. Copiar el proyecto

```bash
git clone https://github.com/<usuario>/iot-monitoreo-ambiental-edge-aws.git
sudo mv iot-monitoreo-ambiental-edge-aws /opt/
sudo chown -R ubuntu:ubuntu /opt/iot-monitoreo-ambiental-edge-aws
cd /opt/iot-monitoreo-ambiental-edge-aws
```

También puedes copiarlo mediante `scp` usando una ruta local a tu propia clave. Nunca guardes la clave dentro del repositorio.

## 3. Instalar dependencias

```bash
sudo apt update
sudo apt install -y python3-venv
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
mkdir -p data
```

## 4. Activar el servicio

El archivo `iot-api.service` está preparado para `/opt/iot-monitoreo-ambiental-edge-aws`.

```bash
sudo cp deploy/aws/iot-api.service /etc/systemd/system/iot-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now iot-api.service
sudo systemctl status iot-api.service
```

Verificar desde la instancia:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/mediciones/ultima
```

El segundo endpoint devuelve `404` hasta que se almacena la primera medición.

## 5. Conectar el edge

En el equipo donde corre el edge, reemplaza `<HOST_EC2>` por el DNS o IP pública actual:

```powershell
$env:API_URL = "http://<HOST_EC2>:8000/mediciones"
$env:CONSOLIDATION_LIMIT = "5"
.\.venv\Scripts\python.exe -m edge.edge_processor
```

Para una prueba automatizada compatible con el proyecto, usa el script disponible en tu copia local o crea una prueba equivalente que apunte a la API pública.

## 6. Producción y baja

Para producción se requiere HTTPS, autenticación, gestión de secretos, monitoreo, respaldos y una base administrada cuando SQLite deje de ser adecuada.

Al finalizar una demostración, elimina únicamente los recursos creados para este proyecto: instancia EC2, volúmenes, security group, key pair, IP elástica, snapshots y otros servicios asociados. Revisa Billing después de la baja.
