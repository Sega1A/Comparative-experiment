"""Servidor C: CoAP. Recibe la alerta por POST coap://.../alerta (UDP 5683)."""
import asyncio
import os
import socket
import time

# Transporte UDP IPv4 simple: no depende de que el contenedor tenga IPv6.
os.environ.setdefault("AIOCOAP_SERVER_TRANSPORT", "simplesocketserver")

import aiocoap
import aiocoap.resource as resource

import comun

PUERTO = int(os.environ.get("PUERTO_COAP", 5683))


class Alerta(resource.Resource):
    async def render_post(self, peticion):
        t = time.time_ns()
        comun.registrar_llegada("coap", peticion.payload, t)
        return aiocoap.Message(code=aiocoap.CHANGED)


async def main():
    comun.crear_esquema()
    comun.vigilar_escenario(os.environ.get("NOMBRE", "coap"))
    sitio = resource.Site()
    sitio.add_resource(["alerta"], Alerta())
    ip = os.environ.get("COAP_BIND") or socket.gethostbyname(socket.gethostname())
    await aiocoap.Context.create_server_context(sitio, bind=(ip, PUERTO))
    print(f"[coap] escuchando en UDP {ip}:{PUERTO}", flush=True)
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
