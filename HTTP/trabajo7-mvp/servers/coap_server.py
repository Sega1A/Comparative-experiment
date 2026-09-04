"""
Servidor CoAP del banco de pruebas.

CoAP corre sobre UDP (puerto 5683). Expone el recurso /data que devuelve
el mismo payload que recibe, igual que el servidor HTTP.

NOTA TECNICA IMPORTANTE (esto merece un parrafo en el informe):
aiocoap usa por defecto un transporte llamado "udp6" que necesita que el
sistema tenga IPv6 habilitado. Muchos contenedores Docker vienen sin IPv6.
Por eso el script detecta si hay IPv6 y, si no lo hay, cambia al transporte
"simplesocketserver", que funciona sobre IPv4 puro.
"""

import os
import socket
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def hay_ipv6() -> bool:
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.close()
        return True
    except OSError:
        return False


def ip_propia() -> str:
    """IPv4 de la maquina/contenedor (simplesocketserver no acepta 0.0.0.0)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # no envia nada, solo resuelve la ruta
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return socket.gethostbyname(socket.gethostname())


# El transporte se decide ANTES de importar aiocoap
if hay_ipv6():
    BIND = (os.getenv("COAP_BIND", "::"), 5683)
    MODO = "udp6 (IPv6 disponible)"
else:
    os.environ["AIOCOAP_SERVER_TRANSPORT"] = "simplesocketserver"
    BIND = (os.getenv("COAP_BIND", ip_propia()), 5683)
    MODO = "simplesocketserver (sin IPv6, usando IPv4)"

import asyncio                          # noqa: E402
import aiocoap                          # noqa: E402
import aiocoap.resource as resource     # noqa: E402


class DataResource(resource.Resource):
    """Recurso /data: eco puro, el mismo trabajo util que el servidor HTTP."""

    async def render_post(self, request):
        return aiocoap.Message(
            code=aiocoap.numbers.codes.Code.CONTENT,
            payload=request.payload,
        )

    async def render_get(self, request):
        return aiocoap.Message(
            code=aiocoap.numbers.codes.Code.CONTENT,
            payload=b"ok",
        )


async def main():
    root = resource.Site()
    root.add_resource(["data"], DataResource())

    await aiocoap.Context.create_server_context(root, bind=BIND)
    logging.info("Servidor CoAP escuchando en %s:%s  [%s]", BIND[0], BIND[1], MODO)
    logging.info("Recurso disponible: coap://<host>:5683/data")

    await asyncio.get_running_loop().create_future()   # corre para siempre


if __name__ == "__main__":
    asyncio.run(main())
