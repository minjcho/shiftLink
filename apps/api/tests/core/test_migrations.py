from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect


def test_migration_roundtrip_and_no_metadata_drift(database):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database.begin() as connection:
        config.attributes["connection"] = connection
        command.check(config)
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        command.check(config)
