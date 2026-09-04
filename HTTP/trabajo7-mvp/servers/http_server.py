"""
Servidor HTTP del banco de pruebas.

Hace exactamente lo mismo que el servidor CoAP y que el eco MQTT:
recibe un payload y lo devuelve tal cual. Asi la comparacion es justa,
porque los tres protocolos hacen el mismo trabajo util.
"""

from fastapi import FastAPI, Request, Response

app = FastAPI(title="Trabajo 7 - Servidor HTTP")


@app.post("/data")
async def data(request: Request):
    """Recibe bytes crudos y los devuelve. Cero logica de negocio a proposito."""
    body = await request.body()
    return Response(content=body, media_type="application/octet-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "protocolo": "HTTP/1.1"}
