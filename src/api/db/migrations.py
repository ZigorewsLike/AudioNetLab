from typing import Callable, List

from sqlalchemy import Engine, Connection
from sqlalchemy import text as sql_text

from src.core.log_system import print_d, print_e
from .models import Base, Track

# Schema the code expects. Bump it and append a step to MIGRATION_STEPS when the models change.
CURRENT_SCHEMA_VERSION = 1

# Name of the table the old track rows are copied out of while it is rebuilt.
_REBUILD_TABLE_NAME = "track_migrate_old"


def _get_user_version(conn: Connection) -> int:
    """Read the schema version stamped into the database file.

    :param conn: Open connection.
    :returns: int - Version, 0 for a database written before the versioning.
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


def _table_exists(conn: Connection, table: str) -> bool:
    """Whether a table is present in the database.

    :param conn: Open connection.
    :param table: Table name.
    :returns: bool - True when the table exists.
    """
    row = conn.execute(
        sql_text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table},
    ).first()
    return row is not None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    """Whether a table has a column.

    :param conn: Open connection.
    :param table: Table name.
    :param column: Column name.
    :returns: bool - True when the column exists.
    """
    rows = conn.execute(sql_text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def _migrate_to_1(conn: Connection) -> None:
    """Bring the flat track table of the first releases to the library schema.

    The table is rebuilt rather than patched with ALTER TABLE ADD COLUMN, because
    SQLite cannot add a column with a REFERENCES clause. A rebuilt table ends up
    byte for byte identical to the one a fresh database gets, so there is only ever
    one schema to reason about.

    :param conn: Open connection inside a transaction.
    :returns: None.
    """
    if not _table_exists(conn, "track"):
        return  # Fresh database, create_all() already made the final table
    if _column_exists(conn, "track", "album_id"):
        return  # Already rebuilt, the step is re-entrant

    print_d("Migrating the track table to the library schema")

    # Paths were stored as the file dialog and the drop event delivered them, so the
    # same file could be listed twice with different separators. Fold them before the
    # path column becomes unique.
    conn.execute(sql_text("UPDATE track SET path = REPLACE(path, '\\', '/')"))
    removed = conn.execute(
        sql_text("DELETE FROM track WHERE id NOT IN (SELECT MIN(id) FROM track GROUP BY path)")
    ).rowcount
    if removed:
        print_d(f"Removed {removed} duplicate track rows")

    # An index keeps its own name when its table is renamed, so the old ones have to
    # go before the new table claims those names.
    for index_name in ("ix_track_path", "ix_track_title", "ix_track_id"):
        conn.execute(sql_text(f"DROP INDEX IF EXISTS {index_name}"))

    conn.execute(sql_text(f"DROP TABLE IF EXISTS {_REBUILD_TABLE_NAME}"))
    conn.execute(sql_text(f"ALTER TABLE track RENAME TO {_REBUILD_TABLE_NAME}"))

    Track.__table__.create(bind=conn)

    # Everything the old rows did not carry stays NULL and is filled by the first scan.
    # title_key gets an ASCII fold now so search works on the old rows before that scan.
    conn.execute(sql_text(f"""
        INSERT INTO track (id, title, title_key, path, dt_create, dt_last_opened, is_missing, play_count)
        SELECT id, title, lower(title), path, dt_create, dt_last_opened, 0, 0 FROM {_REBUILD_TABLE_NAME}
    """))
    conn.execute(sql_text(f"DROP TABLE {_REBUILD_TABLE_NAME}"))


# One callable per version, index 0 upgrades a version 0 database to version 1.
MIGRATION_STEPS: List[Callable[[Connection], None]] = [
    _migrate_to_1,
]


def migrate(engine: Engine) -> int:
    """Make the database match the models, creating and upgrading as needed.

    This is the single entry point: it creates the missing tables and then runs the
    upgrade steps the stamped version is behind on, in one transaction each.

    :param engine: Engine of the database to upgrade.
    :returns: int - Schema version after the run.
    """
    assert len(MIGRATION_STEPS) == CURRENT_SCHEMA_VERSION, "A migration step per version is required"

    # Adds the tables a new release introduced, existing tables are left untouched
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        version = _get_user_version(conn)

    if version >= CURRENT_SCHEMA_VERSION:
        return version
    if version > 0:
        print_d(f"Database schema {version} -> {CURRENT_SCHEMA_VERSION}")

    for step_index in range(version, CURRENT_SCHEMA_VERSION):
        try:
            with engine.begin() as conn:
                MIGRATION_STEPS[step_index](conn)
                _set_user_version(conn, step_index + 1)
        except Exception as e:
            # The transaction is rolled back, the database stays on the previous version
            print_e(f"Migration to schema {step_index + 1} failed", e)
            raise

    return CURRENT_SCHEMA_VERSION
