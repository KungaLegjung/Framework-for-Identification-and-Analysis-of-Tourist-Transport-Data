# socket_events.py
from datetime import datetime
from flask import session, current_app
from flask_socketio import join_room, emit
from extensions import socketio  # your Socket.IO extension
from db import db_cursor

def _save_chat(room, sender_type, sender_id, receiver_type, receiver_id, message):
    """Save chat into DB and return a message dict."""
    now = datetime.utcnow()
    new_id = None
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO chat (room, sender_type, sender_id, receiver_type, receiver_id, message, timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (room, sender_type, sender_id, receiver_type, receiver_id, message, now),
            )
            if conn:
                conn.commit()
            try:
                new_id = getattr(cur, "lastrowid", None)
            except Exception:
                new_id = None
    except Exception:
        current_app.logger.exception("socket _save_chat DB error")
    msg = {
        "id": new_id,
        "room": room,
        "sender_type": sender_type,
        "sender_id": sender_id,
        "receiver_type": receiver_type,
        "receiver_id": receiver_id,
        "message": message,
        "timestamp": now.isoformat(),
    }
    return msg

@socketio.on("join")
def handle_join(data):
    """
    Expected data: { room: "user_5_admin" }
    Server will add the socket to that room.
    """
    room = (data or {}).get("room")
    if not room:
        return
    try:
        join_room(room)
        current_app.logger.debug(f"Socket {str(session.get('_id', 'n/a'))} joined room {room}")
        emit("joined", {"room": room}, room=room)
    except Exception:
        current_app.logger.exception("handle_join error")

@socketio.on("send_message")
def handle_send_message(data):
    """
    Real-time send message handler.
    Client should send: { room, message, sender_type? (optional), sender_id? (optional), user_id? (optional) }
    We validate sender from session (prefer server session values).
    """
    if not data:
        return

    room = data.get("room")
    message = (data.get("message") or "").strip()
    if not room or not message:
        return

    # determine sender type and id from server session to avoid spoof
    if session.get("role") == "admin":
        sender_type = "admin"
        sender_id = session.get("admin_id")
        receiver_type = "user"
        # try to infer user id from payload 'user_id' or from room name
        receiver_id = data.get("user_id")
        if not receiver_id:
            # attempt to parse 'user_<id>_admin'
            try:
                parts = (room or "").split("_")
                if len(parts) >= 3 and parts[0] == "user":
                    receiver_id = int(parts[1])
            except Exception:
                receiver_id = None
    else:
        # default to user sender
        sender_type = "user"
        sender_id = session.get("user_id")
        receiver_type = "admin"
        receiver_id = None

    # Save chat to DB (returns msg dict)
    msg = _save_chat(room, sender_type, sender_id, receiver_type, receiver_id, message)

    # Emit to the given room and a couple of alternate rooms (robustness)
    try:
        emit("new_message", msg, room=room)
        # also emit to likely alt rooms (e.g. 'user_5' and 'user_5_admin')
        # infer user id if we have it (receiver_id or parse room)
        uid = receiver_id
        if uid is None:
            try:
                parts = (room or "").split("_")
                if len(parts) >= 3 and parts[0] == "user":
                    uid = int(parts[1])
            except Exception:
                uid = None
        if uid:
            alt_rooms = {f"user_{uid}", f"user_{uid}_admin"}
            for ar in alt_rooms:
                if ar != room:
                    try:
                        emit("new_message", msg, room=ar)
                    except Exception:
                        current_app.logger.exception(f"emit to alt room {ar} failed")
    except Exception:
        current_app.logger.exception("SocketIO emit error in handle_send_message")
