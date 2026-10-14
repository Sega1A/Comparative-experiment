"""Resume la ultima corrida: tabla en pantalla, CSV, copia de la base y grafico."""
import csv
import os
import shutil
import statistics
import sys

import comun

SALIDA = os.environ.get("SALIDA", "/salida")
PROTOCOLOS = ["http", "mqtt", "coap"]
COLOR = {"http": "#2a78d6", "mqtt": "#eb6834", "coap": "#1baf7a"}
MARCA = {"http": "o", "mqtt": "s", "coap": "^"}


def percentil(valores, p):
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def cargar():
    comun.crear_esquema()
    bd = comun.bd()
    fila = bd.execute("SELECT corrida FROM envios ORDER BY rowid DESC LIMIT 1").fetchone()
    if not fila:
        sys.exit("No hay datos. Primero ejecuta: docker compose run --rm dispositivo")
    corrida = os.environ.get("CORRIDA") or fila[0]
    filas = bd.execute("""
        SELECT e.id, e.escenario, e.netem, e.protocolo, e.n, e.confirmado,
               (MIN(l.t_llegada_ns) - e.t_envio_ns) / 1e6 AS latencia_ms,
               (e.t_conf_ns - e.t_envio_ns) / 1e6 AS confirmacion_ms,
               e.bytes_payload, e.bytes_tx, e.bytes_rx, e.cpu_ms,
               COUNT(l.id) AS llegadas, e.error
        FROM envios e LEFT JOIN llegadas l ON l.id = e.id
        WHERE e.corrida = ? GROUP BY e.id ORDER BY e.rowid""", (corrida,)).fetchall()
    columnas = ["id", "escenario", "netem", "protocolo", "n", "confirmado", "latencia_ms",
                "confirmacion_ms", "bytes_payload", "bytes_tx", "bytes_rx", "cpu_ms",
                "llegadas", "error"]
    bd.close()
    return corrida, [dict(zip(columnas, f)) for f in filas]


def resumir(detalle):
    escenarios = list(dict.fromkeys(d["escenario"] for d in detalle))
    resumen = []
    for esc in escenarios:
        for p in PROTOCOLOS:
            d = [x for x in detalle if x["escenario"] == esc and x["protocolo"] == p]
            if not d:
                continue
            lat = [x["latencia_ms"] for x in d if x["llegadas"]]
            conf = [x["confirmacion_ms"] for x in d if x["confirmado"]]
            resumen.append({
                "escenario": esc, "netem": d[0]["netem"] or "sin degradacion", "protocolo": p,
                "enviadas": len(d),
                "entregadas": len(lat),
                "entrega_pct": round(100 * len(lat) / len(d), 1),
                "confirmadas_pct": round(100 * len(conf) / len(d), 1),
                "duplicadas": sum(x["llegadas"] - 1 for x in d if x["llegadas"] > 1),
                "lat_mediana_ms": round(statistics.median(lat), 1) if lat else None,
                "lat_media_ms": round(statistics.mean(lat), 1) if lat else None,
                "lat_p95_ms": round(percentil(lat, 95), 1) if lat else None,
                "lat_max_ms": round(max(lat), 1) if lat else None,
                "conf_mediana_ms": round(statistics.median(conf), 1) if conf else None,
                "payload_bytes": d[0]["bytes_payload"],
                "red_bytes_media": round(statistics.mean(x["bytes_tx"] + x["bytes_rx"] for x in d)),
                "cpu_ms_media": round(statistics.mean(x["cpu_ms"] for x in d), 2),
            })
    return escenarios, resumen


def guardar_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def imprimir(corrida, resumen):
    print(f"\nCorrida {corrida}\n")
    cab = (f"{'escenario':<13}{'protocolo':<10}{'entrega':>8}{'confirm.':>9}"
           f"{'mediana':>10}{'p95':>10}{'max':>10}{'bytes red':>11}{'CPU ms':>8}")
    print(cab + "\n" + "-" * len(cab))
    anterior = None
    for r in resumen:
        if anterior not in (None, r["escenario"]):
            print()
        anterior = r["escenario"]
        ms = lambda v: f"{v:>7.0f} ms" if v is not None else f"{'-':>10}"
        print(f"{r['escenario']:<13}{r['protocolo']:<10}{r['entrega_pct']:>7.1f}%"
              f"{r['confirmadas_pct']:>8.1f}%{ms(r['lat_mediana_ms'])}{ms(r['lat_p95_ms'])}"
              f"{ms(r['lat_max_ms'])}{r['red_bytes_media']:>11}{r['cpu_ms_media']:>8.2f}")
    print("\nlatencia = llegada al servidor - envio | bytes red = trafico total medio por alerta")


def graficar(ruta, corrida, escenarios, resumen):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tinta, tenue = "#1f1f1e", "#6b6a63"
    dato = {(r["escenario"], r["protocolo"]): r for r in resumen}
    presentes = [p for p in PROTOCOLOS if any(r["protocolo"] == p for r in resumen)]
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.8), facecolor="white")
    x = range(len(escenarios))
    ancho = 0.26

    def pos(i, p):
        return i + (presentes.index(p) - (len(presentes) - 1) / 2) * ancho

    # 1) Latencia: mediana (marcador) y p95 (extremo de la linea), escala log
    ax = ejes[0]
    for p in presentes:
        xs, med, p95 = [], [], []
        for i, e in enumerate(escenarios):
            r = dato.get((e, p))
            if r and r["lat_mediana_ms"] is not None:
                xs.append(pos(i, p)); med.append(max(r["lat_mediana_ms"], 0.1)); p95.append(max(r["lat_p95_ms"], 0.1))
        ax.vlines(xs, med, p95, color=COLOR[p], linewidth=2)
        ax.plot(xs, med, MARCA[p], color=COLOR[p], markersize=9, markeredgecolor="white",
                markeredgewidth=1.5, linestyle="none", label=p.upper())
        for xi, m in zip(xs, med):
            ax.annotate(f"{m:.0f}", (xi, m), textcoords="offset points", xytext=(0, -15),
                        ha="center", fontsize=8, color=tinta)
    ax.set_yscale("log")
    ax.margins(y=0.18)
    ax.set_title("Latencia de entrega (ms)\nmediana y linea hasta el percentil 95, escala log",
                 fontsize=10, color=tinta, loc="left")

    # 2) y 3) Barras
    for ax, campo, titulo, fmt in (
            (ejes[1], "entrega_pct", "Alertas entregadas (%)", "{:.0f}"),
            (ejes[2], "red_bytes_media", "Trafico de red por alerta (bytes)\nincluye conexion, ACK y retransmisiones", "{:.0f}")):
        for p in presentes:
            xs = [pos(i, p) for i, e in enumerate(escenarios) if (e, p) in dato]
            ys = [dato[(e, p)][campo] for e in escenarios if (e, p) in dato]
            barras = ax.bar(xs, ys, width=ancho - 0.03, color=COLOR[p], label=p.upper())
            ax.bar_label(barras, labels=[fmt.format(y) for y in ys], fontsize=8, color=tinta, padding=2)
        ax.set_title(titulo, fontsize=10, color=tinta, loc="left")
        ax.set_ylim(0, 112 if campo == "entrega_pct" else None)

    for ax in ejes:
        ax.set_xticks(list(x), escenarios, fontsize=9)
        ax.tick_params(colors=tenue, length=0)
        ax.grid(axis="y", color="#e6e5df", linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color("#c9c8c0")
    ejes[0].legend(frameon=False, fontsize=9, loc="lower right", labelcolor=tinta)
    fig.suptitle(f"HTTP, MQTT y CoAP bajo red degradada (corrida {corrida})",
                 fontsize=12, color=tinta, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(ruta, dpi=150)


if __name__ == "__main__":
    corrida, detalle = cargar()
    escenarios, resumen = resumir(detalle)
    imprimir(corrida, resumen)
    os.makedirs(SALIDA, exist_ok=True)
    guardar_csv(os.path.join(SALIDA, "resumen.csv"), resumen)
    guardar_csv(os.path.join(SALIDA, "detalle.csv"), detalle)
    shutil.copy(comun.BD, os.path.join(SALIDA, "resultados.db"))
    graficar(os.path.join(SALIDA, "comparativa.png"), corrida, escenarios, resumen)
    print(f"\nArchivos en la carpeta resultados/: resumen.csv, detalle.csv, resultados.db, comparativa.png")
