# Cambios respecto al código de Pedro

La lógica académica central se conserva:

1. Suscripción MQTT a `nodo/esp32/sensores`.
2. Validación de `nodo_id`, `temp`, `hum`, `co` y `pm25`.
3. Acumulación de muestras.
4. Cálculo de promedios al alcanzar el límite.
5. Construcción del paquete con gateway, nodo, fecha y estado.

Se corrigió únicamente lo necesario para formar el flujo completo:

- La salida llamada `TOPIC_CLOUD` seguía publicando en `localhost`. Ahora el
  paquete consolidado se envía mediante HTTP a `POST /mediciones`.
- Se agregó validación numérica y rango para CO.
- Los buffers se separaron por `nodo_id` para no mezclar distintos ESP32.
- El buffer se limpia solo después de una respuesta HTTP exitosa.
- Se añadieron reintentos HTTP, reconexión MQTT y suscripción al reconectar.
- Se actualizó el uso de callbacks para `paho-mqtt` 2.x.
- La cantidad de muestras se configura con `CONSOLIDATION_LIMIT`.

El simulador no reemplaza al proyecto de Sebastián. Implementa exactamente el
contrato JSON que su ESP32 debe publicar para que el equipo pueda probar el
resto del recorrido sin depender del hardware durante el desarrollo.

