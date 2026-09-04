# Instalación en Windows 10/11 con VS Code

Guía completa desde cero. Tiempo estimado: 40–60 minutos, casi todo esperando descargas.

---

## Por qué WSL2 y no Windows "pelado"

WSL2 es un Linux real corriendo dentro de Windows. Lo necesitás porque:

1. **Docker Desktop en Windows usa WSL2 por debajo de todos modos.** No es un paso extra, es el paso.
2. **`escenario_red.sh` no funciona en Windows.** Usa `tc netem`, que es una herramienta del kernel de Linux. Sin WSL2 perdés el Sprint 3, que es donde están los mejores resultados del trabajo.
3. **Los scripts `.sh` son de bash.** En WSL corren tal cual.

VS Code se conecta a WSL de forma transparente: escribís en la ventana de Windows de siempre, pero el código corre en Linux.

---

## Paso 0 — Verificar virtualización

Abrí el **Administrador de tareas** (`Ctrl+Shift+Esc`) → pestaña **Rendimiento** → **CPU**.
Buscá la línea **"Virtualización"**. Debe decir **Habilitado**.

Si dice *Deshabilitado*: hay que activarla en la BIOS/UEFI (reiniciar y entrar con F2, F10, Supr o Esc según la marca; buscar `Intel VT-x`, `AMD-V` o `SVM Mode` y ponerlo en Enabled). Sin esto nada de lo que sigue funciona.

---

## Paso 1 — Instalar WSL2

Abrí **PowerShell como administrador** (botón Inicio → escribí `powershell` → clic derecho → *Ejecutar como administrador*).

```powershell
wsl --install
```

Esto instala WSL2 y Ubuntu de una. **Reiniciá la laptop** cuando termine.

Al reiniciar se abre sola una ventana negra de Ubuntu que pide crear un usuario y contraseña. Esos datos son **solo de Linux**, no tienen nada que ver con tu cuenta de Windows.

> Cuando escribís la contraseña no aparece nada en pantalla, ni asteriscos. Es normal, está escribiendo igual.

Verificá que quedó en versión 2:

```powershell
wsl -l -v
```

Tiene que decir `Ubuntu ... Running ... 2`. Si dice `1`, corré `wsl --set-version Ubuntu 2`.

---

## Paso 2 — Instalar Docker Desktop

1. Bajalo de https://www.docker.com/products/docker-desktop/
2. Durante la instalación, dejá marcado **"Use WSL 2 instead of Hyper-V"**.
3. Reiniciá si te lo pide.
4. Abrí Docker Desktop y esperá a que el ícono de la ballena abajo a la derecha deje de moverse.
5. Andá a **Settings (engranaje) → Resources → WSL Integration** y **activá el switch de Ubuntu**. Dale *Apply & Restart*.

Este último paso es el que más se olvida. Sin él, Docker existe en Windows pero Ubuntu no lo ve.

---

## Paso 3 — Instalar VS Code y sus extensiones

1. Bajá VS Code de https://code.visualstudio.com/
2. Abrilo, andá al ícono de extensiones (los cuadraditos, o `Ctrl+Shift+X`) e instalá:
   - **WSL** (de Microsoft) — la clave de todo
   - **Python** (de Microsoft)
   - **Docker** (de Microsoft)

---

## Paso 4 — Conectar VS Code a WSL

En VS Code apretá `Ctrl+Shift+P`, escribí `WSL: Connect to WSL` y dale Enter.

Se abre una ventana nueva. Abajo a la izquierda, en la barra azul, debe decir **`WSL: Ubuntu`**. Si dice eso, ya estás trabajando dentro de Linux.

Abrí una terminal integrada con `` Ctrl+ñ `` (o menú *Terminal → New Terminal*). Debe verse algo como `tuusuario@DESKTOP-XXXX:~$`.

Comprobá que Docker llegó hasta acá:

```bash
docker --version
docker compose version
```

Si tira `command not found`, volvé al Paso 2 punto 5.

---

## Paso 5 — Meter el proyecto adentro de Linux

Descomprimí `trabajo7-mvp.zip` en tu carpeta de Descargas de Windows (clic derecho → Extraer todo).

Después, en la terminal de VS Code (la de WSL):

```bash
cd ~
cp -r /mnt/c/Users/TU_USUARIO_WINDOWS/Downloads/trabajo7-mvp ./
cd trabajo7-mvp
ls
```

Reemplazá `TU_USUARIO_WINDOWS` por tu nombre de usuario real. Si no lo sabés:

```bash
ls /mnt/c/Users/
```

> **Importante:** el proyecto tiene que vivir en `~/` (el disco de Linux), **no** en `/mnt/c/`. Si lo dejás en el disco de Windows, Docker anda hasta 10 veces más lento y los permisos de los `.sh` se rompen.

Ahora abrí esa carpeta en VS Code: `Ctrl+Shift+P` → `File: Open Folder` → escribí `/home/TU_USUARIO_LINUX/trabajo7-mvp`.

Dale permisos de ejecución a los scripts:

```bash
chmod +x bench/*.sh
```

---

## Paso 6 — Levantar los servidores

```bash
docker compose up -d --build
```

La primera vez tarda varios minutos porque baja las imágenes. Después:

```bash
docker compose ps
```

Los 4 servicios (`t7-mosquitto`, `t7-mqtt-echo`, `t7-http`, `t7-coap`) deben decir **running**.

Probá que responden:

```bash
curl http://localhost:8000/health
docker compose logs coap-server | tail -3
docker compose logs mqtt-echo | tail -3
```

---

## Paso 7 — Preparar el cliente de pruebas

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip

cd bench
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cuando el entorno virtual está activo, el prompt arranca con `(.venv)`.

> Cada vez que abras una terminal nueva tenés que volver a correr `source .venv/bin/activate`. Es el error número uno.

---

## Paso 8 — Correr el experimento

Borrá primero mis datos de ejemplo:

```bash
rm ../resultados/resultados.csv
```

Y corré lo tuyo:

```bash
python bench.py --n 200 --etiqueta corrida1
python analizar.py --etiqueta corrida1
```

Los PNG aparecen en `resultados/`. En el explorador de archivos de VS Code (panel izquierdo) les hacés clic y se abren ahí mismo.

---

## Paso 9 — Los extras (Sprints 2 y 3)

```bash
# CPU y RAM: en OTRA terminal, mientras corre bench.py
cd ~/trabajo7-mvp/bench && source .venv/bin/activate
python medir_recursos.py --segundos 300

# Bytes reales en la red
sudo apt install -y tshark      # elegí "No" cuando pregunte por usuarios no-root
sudo ./capturar_trafico.sh 120

# Simular red mala y repetir
sudo ./escenario_red.sh celular
python bench.py --n 200 --etiqueta celular
sudo ./escenario_red.sh limpiar
python analizar.py              # sin --etiqueta compara todas las corridas
```

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `docker: command not found` en Ubuntu | Falta la integración WSL | Docker Desktop → Settings → Resources → WSL Integration → activar Ubuntu |
| `Cannot connect to the Docker daemon` | Docker Desktop cerrado | Abrilo y esperá a que la ballena se estabilice |
| `port is already allocated` | Algo usa el 8000 o el 1883 | `docker compose down` y volvé a subir, o cambiá el puerto en `docker-compose.yml` |
| `Connection refused` al correr bench.py | Los contenedores no terminaron de arrancar | Esperá 10 segundos más y revisá `docker compose ps` |
| `ModuleNotFoundError: requests` | El venv no está activo | `source .venv/bin/activate` |
| `permission denied: ./capturar_trafico.sh` | Falta el permiso | `chmod +x bench/*.sh` |
| WSL no instala | Virtualización apagada | Paso 0 |

---

## Comandos que vas a usar todos los días

```bash
docker compose up -d          # prender
docker compose down           # apagar
docker compose ps             # ver qué está corriendo
docker compose logs -f mqtt-echo   # ver logs en vivo (Ctrl+C para salir)
docker compose restart        # reiniciar todo
```
