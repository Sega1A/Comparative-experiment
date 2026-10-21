import argparse
import asyncio
import json
import statistics
import sys
import time

import aiocoap
from aiocoap import ACK, Code, Message, Reliable, Unreliable


def valid_alert(sequence: int) -> dict:
    return {
        "device_id": "esp32-01",
        "sequence": sequence,
        "timestamp": int(time.time() * 1000),
    }


async def send(context, base_uri, body, path="alert", tuning=Reliable):
    payload = body if isinstance(body, bytes) else json.dumps(body).encode()
    request = Message(
        code=Code.POST,
        payload=payload,
        transport_tuning=tuning,
        uri=f"{base_uri}/{path}",
    )
    started = time.perf_counter()
    response = await context.request(request).response
    elapsed_ms = (time.perf_counter() - started) * 1000
    return response, elapsed_ms


def report(name, passed, detail):
    print(f"[{'OK' if passed else 'FALLO'}] {name}: {detail}")
    return passed


def describe(response, elapsed_ms):
    return f"{response.mtype.name} {response.code} {response.payload.decode(errors='replace')} ({elapsed_ms:.1f} ms)"


async def run(host, port, repeat):
    base_uri = f"coap://{host}:{port}"
    context = await aiocoap.Context.create_client_context()
    results = []

    try:
        response, ms = await send(context, base_uri, valid_alert(1))
        results.append(
            report(
                "alerta valida CON recibe ACK",
                response.mtype == ACK
                and response.code == Code.CHANGED
                and response.payload == b"true",
                describe(response, ms),
            )
        )

        response, ms = await send(context, base_uri, valid_alert(2), tuning=Unreliable)
        results.append(
            report(
                "alerta valida NON es aceptada",
                response.code == Code.CHANGED and response.payload == b"true",
                describe(response, ms),
            )
        )

        invalid_cases = {
            "faltan campos": {"device_id": "esp32-01"},
            "campo extra": {**valid_alert(3), "extra": "x"},
            "tipo incorrecto": {**valid_alert(3), "sequence": "3"},
            "no es JSON": b"{no es json",
        }
        for name, body in invalid_cases.items():
            response, ms = await send(context, base_uri, body)
            results.append(
                report(
                    f"alerta invalida ({name}) da 4.00",
                    response.code == Code.BAD_REQUEST and response.payload == b"false",
                    describe(response, ms),
                )
            )

        response, ms = await send(context, base_uri, valid_alert(4), path="otra")
        results.append(
            report(
                "ruta desconocida da 4.04",
                response.code == Code.NOT_FOUND,
                describe(response, ms),
            )
        )

        latencies = []
        failures = 0
        for index in range(repeat):
            response, ms = await send(context, base_uri, valid_alert(100 + index))
            latencies.append(ms)
            if response.code != Code.CHANGED:
                failures += 1
        results.append(
            report(
                f"{repeat} alertas CON seguidas",
                failures == 0,
                f"{failures} fallos, latencia media {statistics.mean(latencies):.1f} ms, "
                f"maxima {max(latencies):.1f} ms",
            )
        )
    except aiocoap.error.Error as error:
        print(f"[FALLO] no se pudo hablar con {base_uri}: {error!r}")
        print(
            "Revisa que el servidor este corriendo y que el puerto UDP 5683 este publicado."
        )
        return False
    finally:
        await context.shutdown()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} pruebas correctas")
    return all(results)


def main():
    parser = argparse.ArgumentParser(
        description="Prueba rapida del servidor CoAP de alertas."
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5683)
    parser.add_argument(
        "--repeat",
        type=int,
        default=20,
        help="alertas CON seguidas para medir latencia",
    )
    args = parser.parse_args()
    sys.exit(0 if asyncio.run(run(args.host, args.port, args.repeat)) else 1)


if __name__ == "__main__":
    main()
