import json

import pytest
from pydantic import ValidationError

from common.schemas import Person, Settings, get_settings


def test_person_accepts_valid_json():
    person = Person.model_validate_json('{"name": "Ana", "age": 70}')
    assert person.name == "Ana"
    assert person.age == 70


@pytest.mark.parametrize(
    "raw",
    [
        '{"name": "", "age": 70}',
        '{"name": "Ana", "age": -1}',
        '{"name": "Ana", "age": "seventy"}',
        '{"name": "Ana"}',
        '{"name": "Ana", "age": 70, "extra": true}',
        '{"name": "Ana", "age": 70',
    ],
)
def test_person_rejects_invalid_json(raw):
    with pytest.raises(ValidationError):
        Person.model_validate_json(raw)


def test_person_serializes_to_dict_and_json():
    person = Person(name="Ana", age=70)
    assert person.model_dump(mode="json") == {"name": "Ana", "age": 70}
    assert json.loads(person.model_dump_json()) == {"name": "Ana", "age": 70}


def test_settings_reads_database_url_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_USER=alerts\nDATABASE_URL=postgresql://user:pass@localhost:5432/alerts\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "postgresql://user:pass@localhost:5432/alerts"


def test_environment_variable_overrides_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://from-file/db\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-env/db")
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "postgresql://from-env/db"


def test_settings_fails_when_database_url_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    empty_env_file = tmp_path / ".env"
    empty_env_file.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings(_env_file=empty_env_file)


def test_get_settings_returns_cached_instance(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://cached/db")
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
        assert get_settings().database_url == "postgresql://cached/db"
    finally:
        get_settings.cache_clear()
