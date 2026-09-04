#!/usr/bin/env bash
# ==========================================================
# Captura de trafico para medir "tamano de mensajes"
# (indicador exigido por el enunciado del Trabajo 7)
#
# Requiere tshark:  sudo apt install tshark
#
# Uso:
#   Terminal A:  sudo ./capturar_trafico.sh 120
#   Terminal B:  python bench.py --protocolos coap mqtt-qos1 http
#
# Genera: resultados/captura.pcap  y  resultados/bytes_por_protocolo.txt
# ==========================================================

set -e

DUR=${1:-120}
DIR="$(cd "$(dirname "$0")/.." && pwd)/resultados"
mkdir -p "$DIR"

# En Linux el trafico a localhost va por la interfaz loopback
IFACE=${IFACE:-lo}

echo "Capturando ${DUR}s en la interfaz ${IFACE}..."
tshark -i "$IFACE" -a duration:"$DUR" \
  -f "tcp port 1883 or tcp port 8000 or udp port 5683" \
  -w "$DIR/captura.pcap"

echo ""
echo "=== BYTES TOTALES POR PROTOCOLO ===" | tee "$DIR/bytes_por_protocolo.txt"

for filtro in "tcp.port==1883:MQTT" "tcp.port==8000:HTTP" "udp.port==5683:CoAP"; do
  f="${filtro%%:*}"
  nombre="${filtro##*:}"
  linea=$(tshark -r "$DIR/captura.pcap" -Y "$f" -T fields -e frame.len \
          | awk -v n="$nombre" '{s+=$1; c++} END {
              if (c>0) printf "%-6s paquetes=%-7d bytes_totales=%-10d bytes_promedio=%.1f\n", n, c, s, s/c;
              else printf "%-6s sin paquetes\n", n }')
  echo "$linea" | tee -a "$DIR/bytes_por_protocolo.txt"
done

echo ""
echo "Captura completa en $DIR/captura.pcap"
echo "Abrila en Wireshark para las capturas de pantalla del informe."
