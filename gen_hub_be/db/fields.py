import json
from django.conf import settings
from django.db import connection, models

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


class FlexibleJSONField(SQLiteJSONField):
    """
    Stores JSON in SQLite while transparently leveraging PostgreSQL's native JSONField when available.
    """

    def db_type(self, connection):
        if connection.vendor == "postgresql" and PostgresJSONField:
            return PostgresJSONField().db_type(connection)
        return super().db_type(connection)

    def from_db_value(self, value, expression, connection):
        if connection.vendor == "postgresql":
            return value
        return super().from_db_value(value, expression, connection)

    def get_prep_value(self, value):
        if is_postgres_backend():
            return value
        return super().get_prep_value(value)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        if value is None:
            return ""
        if is_postgres_backend():
            return json.dumps(value)
        return super().value_to_string(obj)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = "gen_hub_be.db.fields.FlexibleJSONField"
        return name, path, args, kwargs


__all__ = ["FlexibleJSONField", "is_postgres_backend"]
