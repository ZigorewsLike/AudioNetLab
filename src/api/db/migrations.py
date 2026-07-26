from typing import Callable, List

from sqlalchemy import Engine, Connection
from sqlalchemy import text as sql_text

from src.core.log_system import print_d, print_e
from .models import Base

# Schema version the tables in models.py describe. A brand new database is created at
# this version directly; there is nothing to upgrade from yet.
#
# To change the schema later: edit the models, append a step to MIGRATION_STEPS and the
# version bumps itself. MIGRATION_STEPS[i] upgrades a database from schema version
# (i + 1) to (i + 2), so a database at version v runs steps[v-1 ..].
def _column_exists(conn: Connection, table: str, column: str) -> bool:
    """Whether a table already has a column.

    :param conn: Open connection.
    :param table: Table name.
    :param column: Column name.
    :returns: bool - True when the column is present.
    """
    rows = conn.execute(sql_text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def _migrate_to_2(conn: Connection) -> None:
    """Add the bits_per_sample column the album page shows per track.

    A fresh database already has it from the models, this fills it in on a database
    made before the column existed. Existing rows stay NULL until the next scan reads
    the value from the files.

    :param conn: Open connection inside a transaction.
    :returns: None.
    """
    if not _column_exists(conn, "track", "bits_per_sample"):
        conn.execute(sql_text("ALTER TABLE track ADD COLUMN bits_per_sample INTEGER"))


BASELINE_SCHEMA_VERSION = 1
MIGRATION_STEPS: List[Callable[[Connection], None]] = [
    _migrate_to_2,
]
CURRENT_SCHEMA_VERSION = BASELINE_SCHEMA_VERSION + len(MIGRATION_STEPS)


def _get_user_version(conn: Connection) -> int:
    """Read the schema version stamped into the database file.

    :param conn: Open connection.
    :returns: int - Version, 0 for a database that was just created.
    """
    return int(conn.execute(sql_text("PRAGMA user_version")).scalar() or 0)


def _set_user_version(conn: Connection, version: int) -> None:
    """Stamp the schema version into the database file.

    :param conn: Open connection.
    :param version: Version to write.
    :returns: None.
    """
    # PRAGMA does not accept bound parameters, the value is an int so it cannot inject
    conn.execute(sql_text(f"PRAGMA user_version = {int(version)}"))


def migrate(engine: Engine) -> int:
    """Make the database match the models, creating and upgrading as needed.

    The single entry point: it creates the missing tables and then runs the upgrade
    steps the stamped version is behind on, each in its own transaction, so a failed
    upgrade leaves the file on the previous version.

    :param engine: Engine of the database to prepare.
    :returns: int - Schema version after the run.
    """
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        version = _get_user_version(conn)

    # A fresh database reads version 0, but create_all just built the current schema,
    # so it only needs to be stamped, not upgraded.
    if version == 0:
        with engine.begin() as conn:
            _set_user_version(conn, CURRENT_SCHEMA_VERSION)
        return CURRENT_SCHEMA_VERSION

    if version >= CURRENT_SCHEMA_VERSION:
        return version

    print_d(f"Database schema {version} -> {CURRENT_SCHEMA_VERSION}")
    for step_index in range(version - 1, CURRENT_SCHEMA_VERSION - 1):
        try:
            with engine.begin() as conn:
                MIGRATION_STEPS[step_index](conn)
                _set_user_version(conn, step_index + 2)
        except Exception as e:
            # The transaction is rolled back, the database stays on the previous version
            print_e(f"Migration to schema {step_index + 2} failed", e)
            raise

    return CURRENT_SCHEMA_VERSION
