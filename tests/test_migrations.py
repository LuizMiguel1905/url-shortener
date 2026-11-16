from alembic import command
from alembic.config import Config


def test_models_match_migrations(alembic_config: Config) -> None:
    command.check(alembic_config)


def test_downgrade_and_upgrade_roundtrip(alembic_config: Config) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
