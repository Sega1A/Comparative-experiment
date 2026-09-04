"""
Analisis de resultados del banco de pruebas.

Lee resultados/resultados.csv y produce:
  - resultados/tabla_resumen.csv   -> la tabla que va en el informe
  - resultados/fig1_latencia_por_protocolo.png
  - resultados/fig2_latencia_vs_payload.png
  - resultados/fig3_distribucion.png

Uso:
    python analizar.py
    python analizar.py --etiqueta corrida1
"""

import argparse
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent / "resultados"
CSV = BASE / "resultados.csv"

ORDEN = ["http-noka", "http", "coap", "mqtt-qos0", "mqtt-qos1", "mqtt-qos2"]


def cargar(etiqueta=None):
    if not CSV.exists():
        raise SystemExit(f"No existe {CSV}. Corre primero: python bench.py")
    df = pd.read_csv(CSV)
    if etiqueta:
        df = df[df["etiqueta"] == etiqueta]
    if df.empty:
        raise SystemExit("El CSV no tiene datos para esa etiqueta.")
    return df


def tabla_resumen(df):
    """Tabla agregada: es literalmente la tabla del capitulo de resultados."""
    t = df.groupby(["protocolo", "payload_bytes"])["rtt_ms"].agg(
        n="count",
        media="mean",
        mediana="median",
        p95=lambda s: s.quantile(0.95),
        p99=lambda s: s.quantile(0.99),
        minimo="min",
        maximo="max",
        desv_std="std",
    ).round(3).reset_index()

    salida = BASE / "tabla_resumen.csv"
    t.to_csv(salida, index=False)
    print(f"\n== TABLA RESUMEN ==\n{t.to_string(index=False)}")
    print(f"\nGuardada en {salida}")
    return t


def fig_latencia_por_protocolo(df):
    """Barras: latencia media por protocolo (promediando todos los payloads)."""
    g = df.groupby("protocolo")["rtt_ms"].agg(["mean", "std"])
    g = g.reindex([p for p in ORDEN if p in g.index])

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(g.index, g["mean"], yerr=g["std"], capsize=5,
           color="#4C72B0", edgecolor="black", linewidth=0.6)
    ax.set_ylabel("RTT medio (ms)")
    ax.set_xlabel("Protocolo")
    ax.set_title("Figura 1. Latencia media de ida y vuelta por protocolo")
    ax.grid(axis="y", alpha=0.3)
    for i, (v, e) in enumerate(zip(g["mean"], g["std"].fillna(0))):
        ax.text(i, v + e, f"  {v:.2f} ms", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, (g["mean"] + g["std"].fillna(0)).max() * 1.18)
    fig.tight_layout()
    fig.savefig(BASE / "fig1_latencia_por_protocolo.png", dpi=150)
    plt.close(fig)


def fig_latencia_vs_payload(df):
    """Lineas: como escala cada protocolo cuando el mensaje crece."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for proto in [p for p in ORDEN if p in df["protocolo"].unique()]:
        sub = df[df["protocolo"] == proto].groupby("payload_bytes")["rtt_ms"].mean()
        ax.plot(sub.index, sub.values, marker="o", label=proto)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Tamano del payload (bytes, escala log2)")
    ax.set_ylabel("RTT medio (ms)")
    ax.set_title("Figura 2. Latencia frente al tamano del mensaje")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(BASE / "fig2_latencia_vs_payload.png", dpi=150)
    plt.close(fig)


def fig_distribucion(df):
    """Boxplot: muestra la dispersion y los outliers, no solo el promedio."""
    protos = [p for p in ORDEN if p in df["protocolo"].unique()]
    datos = [df[df["protocolo"] == p]["rtt_ms"].values for p in protos]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(datos, showfliers=True, patch_artist=True,
               boxprops=dict(facecolor="#DDE6F0"))
    ax.set_xticks(range(1, len(protos) + 1))
    ax.set_xticklabels(protos)
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Figura 3. Distribucion de latencias (dispersion y valores atipicos)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(BASE / "fig3_distribucion.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", default=None)
    args = ap.parse_args()

    df = cargar(args.etiqueta)
    tabla_resumen(df)
    fig_latencia_por_protocolo(df)
    fig_latencia_vs_payload(df)
    fig_distribucion(df)
    print(f"\n3 figuras generadas en {BASE}\n")


if __name__ == "__main__":
    main()
