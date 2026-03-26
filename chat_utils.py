# chat_utils.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _try_execute(cur, sql, params):
    """
    Try executing with %s placeholders (MySQL/PyMySQL), but fallback to ? if sqlite raises.
    Returns True on success.
    """
    try:
        cur.execute(sql, params)
        return True
    except Exception as e:
        # fallback for sqlite which uses ? placeholders
        # convert %s -> ? and try again
        msg = str(e).lower()
        if "sqlite" in msg or "operationalerror" in msg or "%" in sql:
            try:
                alt_sql = sql.replace("%s", "?")
                cur.execute(alt_sql, params)
                return True
            except Exception:
                # log original error and re-raise later
                logger.debug("Fallback execute failed", exc_info=True)
                raise
        raise

def save_chat_message(db_cursor_factory, room, sender_type, sender_id, message_text, receiver_id=None, receiver_type="admin"):
    """
    Persist the message in the `chat` table and return a dict representing the saved message.
    - db_cursor_factory : your `db_cursor` context manager from db.py
    - room, sender_type, sender_id, message_text: required
    - receiver_id, receiver_type: optional
    Returns message dict on success, None on failure.
    """
    if not (room and message_text and sender_type):
        return None

    now = datetime.utcnow()
    try:
        # Use provided db_cursor context manager
        with db_cursor_factory() as (conn, cur):
            sql = """
            INSERT INTO chat (room, sender_type, sender_id, receiver_type, receiver_id, message, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (room, sender_type, sender_id, receiver_type, receiver_id, message_text, now)
            _try_execute(cur, sql, params)
            if conn:
                try:
                    conn.commit()
                except Exception:
                    # some DB wrappers commit on context exit; ignore commit failure but log
                    logger.debug("commit failed/ignored", exc_info=True)

            # determine inserted id if available
            new_id = None
            try:
                new_id = getattr(cur, "lastrowid", None)
                if new_id is None:
                    # some cursor implementations return rowcount and not lastrowid
                    pass
            except Exception:
                new_id = None

            msg = {
                "id": new_id,
                "room": room,
                "sender_type": sender_type,
                "sender_id": sender_id,
                "receiver_type": receiver_type,
                "receiver_id": receiver_id,
                "message": message_text,
                "timestamp": now.isoformat(),
            }
            return msg
    except Exception:
        logger.exception("save_chat_message failed")
        return None
