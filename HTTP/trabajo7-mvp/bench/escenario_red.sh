#!/usr/bin/env bash
# ==========================================================
# Simula redes malas usando tc netem (Linux).
#
# Esto es lo que convierte el trabajo en un experimento IoT de verdad:
# en una red perfecta los tres protocolos se parecen. La diferencia
# aparece cuando hay perdida de paquetes y latencia, que es justo el
# escenario real de un sensor conectado por celular o LoRa.
#
# Requiere:  sudo apt install iproute2
#
# Uso:
#   sudo ./escenario_red.sh wifi        # 20ms de retardo
#   sudo ./escenario_red.sh celular     # 100ms + 2% perdida
#   sudo ./escenario_red.sh pesima      # 300ms + 10% perdida
#   sudo ./escenario_red.sh limpiar     # quitar todo
#
# Despues de aplicar un escenario, corre el benchmark con una etiqueta:
#   python bench.py --n 200 --etiqueta celular
# ==========================================================

set -e

IFACE=${IFACE:-lo}
ESC=${1:-limpiar}

limpiar() {
  tc qdisc del dev "$IFACE" root 2>/dev/null || true
  echo "Reglas de red eliminadas en $IFACE"
}

case "$ESC" in
  wifi)
    limpiar
    tc qdisc add dev "$IFACE" root netem delay 20ms 5ms
    echo "Escenario WIFI: 20ms +/- 5ms de jitter"
    ;;
  celular)
    limpiar
    tc qdisc add dev "$IFACE" root netem delay 100ms 20ms loss 2%
    echo "Escenario CELULAR: 100ms +/- 20ms, 2% de perdida"
    ;;
  pesima)
    limpiar
    tc qdisc add dev "$IFACE" root netem delay 300ms 50ms loss 10%
    echo "Escenario PESIMA: 300ms +/- 50ms, 10% de perdida"
    ;;
  limpiar)
    limpiar
    ;;
  *)
    echo "Escenario desconocido: $ESC"
    echo "Opciones: wifi | celular | pesima | limpiar"
    exit 1
    ;;
esac

echo ""
tc qdisc show dev "$IFACE"
