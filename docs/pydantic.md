# Guía de Pydantic

El proyecto usa Pydantic v2 para validar datos, convertir objetos a JSON y leer la configuración del archivo `.env`. Todo vive en `common/schemas/`.

```
common/schemas/
├── __init__.py   # exporta Settings, get_settings y los esquemas
├── config.py     # configuración desde variables de entorno y .env
└── example.py    # esquema de ejemplo, se reemplaza luego por los reales
```

Los servidores, el cliente y el módulo de base de datos importan desde `common.schemas`. Nadie define esquemas dentro de `servers/`.

## Instalación

Desde la raíz del repositorio, con el entorno virtual activado:

```bash
pip install -r requirements.txt
```

Para correr además las pruebas:

```bash
pip install -r requirements-dev.txt
pytest
```

Las versiones están fijas en `requirements.txt` (`pydantic==2.14.1`, `pydantic-settings==2.16.0`).

## Definir un esquema

Un esquema es una clase que hereda de `BaseModel`. Cada atributo es un campo, y `Field` agrega reglas.

```python
from pydantic import BaseModel, ConfigDict, Field


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    age: int = Field(ge=0)
```

`extra="forbid"` hace que se rechacen los campos que no están definidos. Sin esa opción, Pydantic los ignora en silencio.

Reglas de `Field` que más se usan:

| Regla | Significado |
|---|---|
| `min_length`, `max_length` | Largo mínimo y máximo de un texto o lista |
| `ge`, `gt` | Mayor o igual, mayor que |
| `le`, `lt` | Menor o igual, menor que |
| `pattern` | Expresión regular que debe cumplir un texto |
| `default` | Valor por defecto, el campo pasa a ser opcional |

## Validar datos

Cuando el dato llega como texto JSON, por ejemplo el cuerpo de una petición:

```python
from pydantic import ValidationError

from common.schemas import Person

try:
    person = Person.model_validate_json('{"name": "Ana", "age": 70}')
except ValidationError as error:
    print(error)
```

Cuando el dato ya es un diccionario, se usa `model_validate`:

```python
person = Person.model_validate({"name": "Ana", "age": 70})
```

Si algo falla, se lanza `ValidationError`. El mensaje dice qué campo falló y por qué, y `error.errors()` devuelve la misma información como lista, útil para responder un 400 con el detalle.

```
1 validation error for Person
age
  Input should be greater than or equal to 0 [type=greater_than_equal, input_value=-1, input_type=int]
```

## Convertir a diccionario o JSON

```python
person.model_dump(mode="json")
person.model_dump_json()
```

`model_dump(mode="json")` devuelve un diccionario con tipos que se pueden guardar directamente, por ejemplo en la columna `payload` (JSONB) de la base de datos. `model_dump_json()` devuelve el texto JSON listo para enviar.

## Leer la configuración

`common/schemas/config.py` define la clase `Settings`, que lee las variables del archivo `.env` de la raíz del repositorio:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
```

Para usarla:

```python
from common.schemas import get_settings

settings = get_settings()
print(settings.database_url)
```

Detalles importantes:

- El nombre del campo se busca sin importar mayúsculas: `database_url` lee `DATABASE_URL`.
- Si la variable existe en el entorno del sistema, tiene prioridad sobre el `.env`. Así un contenedor de Docker puede usar otro valor sin tocar el archivo.
- La ruta del `.env` se calcula desde la raíz del repositorio, así que funciona aunque el programa se ejecute desde otra carpeta.
- `extra="ignore"` permite que el `.env` tenga otras variables, como `POSTGRES_USER`. Sin esa opción, `pydantic-settings` falla al encontrar variables que no son campos de `Settings`.
- `get_settings()` crea la configuración una sola vez y la reutiliza. Si falta una variable obligatoria, lanza `ValidationError` la primera vez que se llama, por eso conviene llamarla al arrancar cada servidor.

Para agregar una variable nueva, se agrega un campo a `Settings` y la línea correspondiente a `.env.example`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    http_port: int = 8000
```

Un campo con valor por defecto es opcional. Pydantic convierte el texto del `.env` al tipo indicado, y falla si no puede, por ejemplo `HTTP_PORT=abc`.

## Agregar un esquema real

1. Crear un archivo en `common/schemas/`, por ejemplo `alert.py`, con la clase del esquema.
2. Exportarla en `common/schemas/__init__.py` y agregarla a `__all__`.
3. Agregar pruebas en `tests/` con al menos un dato válido y uno inválido.
4. Cuando ya existan esquemas reales, borrar `example.py` y sus pruebas.
