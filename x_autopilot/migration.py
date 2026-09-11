"""One-time, transactional copy from a read-only SQLite snapshot into empty PostgreSQL."""

from pathlib import Path
import sqlite3

TABLES = (
    "research_items", "evidence_records", "research_claims", "drafts", "claims",
    "draft_revisions", "pipeline_runs", "model_calls", "publish_claims", "job_slots",
)


def import_sqlite_to_postgres(source_path: str | Path, database_url: str) -> dict[str, int]:
    import psycopg
    from psycopg import sql
    from .postgres import PostgresRepository

    source_path = Path(source_path).resolve(strict=True)
    PostgresRepository(database_url).initialize()
    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    counts = {}
    try:
        source.execute("BEGIN")
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Source SQLite integrity check failed.")
        version = source.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        if not version or version > 4:
            raise ValueError("Unsupported SQLite schema version.")
        available = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with psycopg.connect(database_url, connect_timeout=10) as target:
            with target.cursor() as cursor:
                # Exclude writers for the complete emptiness-check/copy transaction.
                cursor.execute(sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                    sql.SQL(", ").join(map(sql.Identifier, TABLES))))
                for table in TABLES:
                    cursor.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM {})").format(sql.Identifier(table)))
                    if cursor.fetchone()[0]:
                        raise ValueError("PostgreSQL import requires an empty destination; nothing was copied.")
                for table in TABLES:
                    if table not in available:
                        counts[table] = 0
                        continue
                    rows = source.execute(f'SELECT * FROM "{table}"')
                    columns = [description[0] for description in rows.description]
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in columns))
                    count = 0
                    for row in rows:
                        values = dict(row)
                        if table == "claims" and values.get("supported") is not None:
                            values["supported"] = bool(values["supported"])
                        cursor.execute(query, [values[column] for column in columns])
                        count += 1
                    counts[table] = count
                    if "id" in columns:
                        cursor.execute(sql.SQL("SELECT MAX(id) FROM {}").format(sql.Identifier(table)))
                        maximum = cursor.fetchone()[0]
                        if maximum is not None:
                            cursor.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true)", (table, maximum))
    finally:
        source.close()
    return counts
