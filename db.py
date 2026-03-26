# db.py
import os
import sqlite3
from contextlib import contextmanager
import logging
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Try importing pymysql; if not installed we'll use SQLite fallback.
try:
    import pymysql
except Exception:
    pymysql = None

import config

# ---------- Helpers ----------
def _has_mysql_config():
    return bool(getattr(config, "DB_HOST", None) and getattr(config, "DB_USER", None) and getattr(config, "DB_NAME", None))

# Safely translate '%s' placeholders to '?' for SQLite.
# We only replace exact "%s" tokens, not arbitrary '%' characters (so LIKE '%foo%' is preserved).
_placeholder_re = re.compile(r"(?<!%)%s")  # match %s not preceded by another %

def _translate_placeholders(query: str) -> str:
    if "%s" not in query:
        return query
    # Replace all "%s" occurrences with "?"
    return _placeholder_re.sub("?", query)

# Cursor wrapper for sqlite that translates %s -> ? placeholders
class SQLiteCursorWrapper:
    def __init__(self, conn: sqlite3.Connection, cur: sqlite3.Cursor):
        self._conn = conn
        self._cur = cur

    def execute(self, query, params=None):
        try:
            if params is not None and "%s" in query:
                q = _translate_placeholders(query)
                return self._cur.execute(q, params)
            return self._cur.execute(query, params or ())
        except Exception:
            # Re-raise after logging for visibility
            logger.exception("SQLiteCursorWrapper.execute failed for query: %s params: %s", query, params)
            raise

    def executemany(self, query, seq_of_params):
        try:
            if "%s" in query:
                q = _translate_placeholders(query)
                return self._cur.executemany(q, seq_of_params)
            return self._cur.executemany(query, seq_of_params)
        except Exception:
            logger.exception("SQLiteCursorWrapper.executemany failed for query: %s", query)
            raise

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __getattr__(self, name):
        # Forward any other attribute access to the underlying cursor (e.g. lastrowid)
        return getattr(self._cur, name)

# ---------- SQLite context ----------
@contextmanager
def sqlite_cursor(db_path=None, dictionary=False):
    """
    Yields (conn, cursor_wrapper)
    - If dictionary=True, rows returned are sqlite3.Row objects (mapping access).
    """
    db_path = db_path or os.path.join(os.path.dirname(__file__), "instance", "db.sqlite3")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # Enable row factory when dictionary requested
        if dictionary:
            conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        wrapper = SQLiteCursorWrapper(conn, cur)
        yield (conn, wrapper)
    except Exception:
        logger.exception("sqlite_cursor: unexpected exception")
        raise
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

# ---------- PyMySQL context ----------
@contextmanager
def pymysql_cursor(conn_params, dictionary=False):
    """
    Yields (conn, cur)
    Uses pymysql connect params dictionary which should include:
    host, port, user, password, database
    """
    if pymysql is None:
        raise RuntimeError("pymysql not available in this Python environment")
    conn = None
    cur = None
    try:
        conn = pymysql.connect(
            host=conn_params.get("host", "127.0.0.1"),
            port=int(conn_params.get("port", 3306)),
            user=conn_params.get("user"),
            password=conn_params.get("password"),
            db=conn_params.get("database"),
            cursorclass=pymysql.cursors.DictCursor if dictionary else pymysql.cursors.Cursor,
            autocommit=False,
        )
        cur = conn.cursor()
        yield (conn, cur)
    except Exception:
        logger.exception("pymysql_cursor: connection/query error")
        raise
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

# ---------- Public db_cursor ----------
@contextmanager
def db_cursor(dictionary=False):
    """
    Yields (conn, cur)
    - If conn is not None, callers may commit on success.
    - cur is a DB cursor; for sqlite cur is a thin wrapper (see above) that supports %s -> ? conversion.
    """
    # Try MySQL / PyMySQL first if configured
    if pymysql and _has_mysql_config():
        logger.info("db.py: attempting to use PyMySQL (MySQL) backend")
        try:
            params = {
                "host": getattr(config, "DB_HOST", "127.0.0.1"),
                "port": getattr(config, "DB_PORT", 3306),
                "user": getattr(config, "DB_USER", None),
                "password": getattr(config, "DB_PASSWORD", None),
                "database": getattr(config, "DB_NAME", None),
            }
            with pymysql_cursor(params, dictionary=dictionary) as (conn, cur):
                yield (conn, cur)
            return
        except Exception:
            logger.exception("MySQL/PyMySQL connection failed; falling back to SQLite")

    # Fallback to SQLite
    db_path = getattr(config, "SQLITE_PATH", os.path.join(os.path.dirname(__file__), "instance", "db.sqlite3"))
    logger.info("db.py: using SQLite fallback at %s", db_path)
    with sqlite_cursor(db_path, dictionary=dictionary) as (conn, cur):
        yield (conn, cur)
