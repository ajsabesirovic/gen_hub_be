import json
from django.conf import settings
from django.db import connection, models

try:
    from psycopg2.extras import Json
except ImportError:
    Json = None

try:
    from django.contrib.postgres.fields import JSONField as PostgresJSONField
except ImportError:  # pragma: no cover
    PostgresJSONField = None


def is_postgres_backend() -> bool:
    engine = settings.DATABASES["default"]["ENGINE"]
    if "postgresql" in engine.lower():
        return True
    try:
        if connection.connection is not None:
            return connection.vendor == "postgresql"
    except Exception:
        pass
    return False


class SQLiteJSONField(models.TextField):
    description = "Stores JSON structures in SQLite using a text column."

    def from_db_value(self, value, expression, conn):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def get_prep_value(self, value):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = "gen_hub_be.db.fields.SQLiteJSONField"
        return name, path, args, kwargs


class FlexibleJSONField(models.JSONField):
    """
    Uses Django's native JSONField which works with both SQLite and PostgreSQL.
    """

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = "gen_hub_be.db.fields.FlexibleJSONField"
        return name, path, args, kwargs


__all__ = ["FlexibleJSONField", "is_postgres_backend"]
