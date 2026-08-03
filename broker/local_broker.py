from __future__ import annotations

import asyncio
import logging
import os

from amqtt.broker import Broker


async def run_broker() -> None:
    host = os.getenv("MQTT_BROKER_BIND", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    config = {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"{host}:{port}",
            }
        },
        "sys_interval": 10,
        "auth": {"allow-anonymous": True},
        "topic-check": {"enabled": False},
    }
    broker = Broker(config)
    await broker.start()
    logging.getLogger("local_broker").info(
        "Broker MQTT local escuchando en %s:%s.", host, port
    )
    await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_broker())
    except KeyboardInterrupt:
        logging.getLogger("local_broker").info(
            "Broker detenido por el usuario."
        )


if __name__ == "__main__":
    main()

