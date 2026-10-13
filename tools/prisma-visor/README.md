# Visor de la base de datos (Prisma Studio)

Sirve para ver y editar en el navegador las tablas `alertas_http`, `alertas_mqtt` y `alertas_coap`.
Las tablas las crea `common/db` (Python); este visor solo las lee. No define tablas.

## Uso

La base puede ser la compartida del equipo (Supabase) o la local de Docker (`docker compose up -d db`).

```bash
cd tools/prisma-visor
npm install
cp .env.example .env     # primera vez; luego edite DATABASE_URL (ver abajo)
npm run studio
```

Se abre en http://localhost:5555. Para cerrarlo, Ctrl + C.

Si las tablas cambian en `common/db/models.py`, actualice el esquema con `npm run pull`.

## DATABASE_URL

Es la misma URL del `.env` de la raíz del repositorio, pero **sin `+psycopg`**: empieza con `postgresql://`.

- Base compartida: `postgresql://postgres.PROYECTO:CLAVE@aws-0-us-east-2.pooler.supabase.com:5432/postgres`
- Base local: `postgresql://USUARIO:CLAVE@localhost:PUERTO/BASE`

Entre comillas dobles en el `.env` de esta carpeta. Este `.env` tampoco se sube a Git.
