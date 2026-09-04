FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El comando real lo define docker-compose.yml (cada servicio usa uno distinto)
CMD ["python", "--version"]
