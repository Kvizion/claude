"""Database tools.

SQLite works out of the box (standard library). PostgreSQL, MySQL and MSSQL are
supported when their optional drivers are installed (``psycopg2``, ``pymysql``,
``pyodbc``); otherwise those tools return a helpful "driver missing" message.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from config import CONFIG


def _check_db_allowed() -> None:
    if not CONFIG.allow_database:
        raise PermissionError("Database access is disabled (LOCAL_DEV_MCP_ALLOW_DATABASE=false).")


def _rows_to_dicts(cursor) -> list[dict]:
    columns = [c[0] for c in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sqlite_query(database: str, query: str, params: Optional[list] = None,
                 max_rows: int = 500) -> dict:
    """Run a SQL statement against a SQLite database file."""
    _check_db_allowed()
    db_path = CONFIG.check_path(database, write=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        is_select = cursor.description is not None
        if is_select:
            fetched = cursor.fetchmany(max_rows)
            rows = [dict(r) for r in fetched]
            truncated = len(cursor.fetchone() or []) > 0
            return {"database": str(db_path), "columns": list(rows[0].keys()) if rows else [],
                    "row_count": len(rows), "rows": rows, "truncated": truncated}
        conn.commit()
        return {"database": str(db_path), "rows_affected": cursor.rowcount}
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}", "database": str(db_path)}
    finally:
        conn.close()


def sqlite_schema(database: str) -> dict:
    """List tables and their columns for a SQLite database."""
    _check_db_allowed()
    db_path = CONFIG.check_path(database)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {}
        for (name,) in cursor.fetchall():
            cursor.execute(f"PRAGMA table_info('{name}')")
            tables[name] = [
                {"name": col[1], "type": col[2], "notnull": bool(col[3]), "pk": bool(col[5])}
                for col in cursor.fetchall()
            ]
        return {"database": str(db_path), "tables": tables}
    finally:
        conn.close()


def _generic_query(driver: str, connect, query: str, params: Optional[list],
                   max_rows: int) -> dict:
    conn = connect()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        if cursor.description is not None:
            columns = [c[0] for c in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchmany(max_rows)]
            return {"driver": driver, "columns": columns, "row_count": len(rows), "rows": rows}
        conn.commit()
        return {"driver": driver, "rows_affected": cursor.rowcount}
    finally:
        conn.close()


def postgres_query(dsn: str, query: str, params: Optional[list] = None, max_rows: int = 500) -> dict:
    """Run SQL against PostgreSQL (requires psycopg2)."""
    _check_db_allowed()
    try:
        import psycopg2  # type: ignore
    except ImportError:
        return {"error": "psycopg2 not installed.", "hint": "pip install psycopg2-binary"}
    try:
        return _generic_query("postgres", lambda: psycopg2.connect(dsn), query, params, max_rows)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"PostgreSQL error: {exc}"}


def mysql_query(host: str, user: str, password: str, database: str, query: str,
                params: Optional[list] = None, port: int = 3306, max_rows: int = 500) -> dict:
    """Run SQL against MySQL/MariaDB (requires pymysql)."""
    _check_db_allowed()
    try:
        import pymysql  # type: ignore
    except ImportError:
        return {"error": "pymysql not installed.", "hint": "pip install pymysql"}
    try:
        return _generic_query(
            "mysql",
            lambda: pymysql.connect(host=host, user=user, password=password,
                                    database=database, port=port),
            query, params, max_rows,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"MySQL error: {exc}"}


def mssql_query(connection_string: str, query: str, params: Optional[list] = None,
                max_rows: int = 500) -> dict:
    """Run SQL against Microsoft SQL Server (requires pyodbc)."""
    _check_db_allowed()
    try:
        import pyodbc  # type: ignore
    except ImportError:
        return {"error": "pyodbc not installed.", "hint": "pip install pyodbc"}
    try:
        return _generic_query("mssql", lambda: pyodbc.connect(connection_string),
                              query, params, max_rows)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"MSSQL error: {exc}"}


def register(mcp) -> None:
    @mcp.tool()
    def db_sqlite_query(database: str, query: str, params: Optional[list] = None,
                        max_rows: int = 500) -> dict:
        """Execute SQL against a SQLite database file."""
        return sqlite_query(database, query, params, max_rows)

    @mcp.tool()
    def db_sqlite_schema(database: str) -> dict:
        """Show the tables and columns of a SQLite database."""
        return sqlite_schema(database)

    @mcp.tool()
    def db_postgres_query(dsn: str, query: str, params: Optional[list] = None,
                          max_rows: int = 500) -> dict:
        """Execute SQL against PostgreSQL using a libpq DSN (requires psycopg2)."""
        return postgres_query(dsn, query, params, max_rows)

    @mcp.tool()
    def db_mysql_query(host: str, user: str, password: str, database: str, query: str,
                       params: Optional[list] = None, port: int = 3306,
                       max_rows: int = 500) -> dict:
        """Execute SQL against MySQL/MariaDB (requires pymysql)."""
        return mysql_query(host, user, password, database, query, params, port, max_rows)

    @mcp.tool()
    def db_mssql_query(connection_string: str, query: str, params: Optional[list] = None,
                       max_rows: int = 500) -> dict:
        """Execute SQL against Microsoft SQL Server (requires pyodbc)."""
        return mssql_query(connection_string, query, params, max_rows)
