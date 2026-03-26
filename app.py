# app.py
# ------------------------------------------------------------
# Early monkey-patching for async workers (eventlet preferred)
# ------------------------------------------------------------
use_eventlet = False
use_gevent = False

try:
    import eventlet  
    eventlet.monkey_patch(dns=False)
    use_eventlet = True
except Exception:
    try:
        from gevent import monkey as gevent_monkey  
        gevent_monkey.patch_all()
        use_gevent = True
    except Exception:
        pass

# ------------------------------------------------------------
# Standard imports (after monkey-patch)
# ------------------------------------------------------------
import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, current_app, jsonify, session
import config
from werkzeug.middleware.proxy_fix import ProxyFix

os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# App factory
# ------------------------------------------------------------
def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    try:
        app.config.from_object(config)
    except Exception:
        logger.exception("Failed to load config.py")

    # Optional: when behind a proxy
    try:
        if app.config.get("USE_PROXY_FIX", False):
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
            logger.info("ProxyFix enabled")
    except Exception:
        logger.exception("ProxyFix apply failed (non-fatal)")

    @app.context_processor
    def inject_config_keys():
        return {
            "GOOGLE_MAPS_API_KEY": app.config.get("GOOGLE_MAPS_API_KEY"),
            "ENABLE_SOCKETIO": app.config.get("ENABLE_SOCKETIO", True),
        }

    app.secret_key = app.config.get("SECRET_KEY", "devkey")

    upload_folder = app.config.get("UPLOAD_FOLDER", os.path.join(app.root_path, "static", "uploads"))
    os.makedirs(upload_folder, exist_ok=True)

    try:
        from blueprints.user import user_bp  
        from blueprints.admin import admin_bp  
        app.register_blueprint(user_bp)
        app.register_blueprint(admin_bp)
    except Exception:
        logger.exception("Failed to import/register user/admin blueprints")

    try:
        from blueprints.map_routes import map_bp  
        app.register_blueprint(map_bp)
    except Exception:
        logger.debug("map_routes blueprint not loaded (optional)")

    # -----------------------------
    # Routes
    # -----------------------------
    @app.route("/")
    def home():
        tpl = os.path.join(app.template_folder or "templates", "shared", "index.html")
        if os.path.exists(tpl):
            return render_template("shared/index.html")
        return (
            "<h1>Tourist Transport System</h1>"
            "<ul>"
            "<li><a href='/user-login'>User Login</a></li>"
            "<li><a href='/signup'>User Signup</a></li>"
            "<li><a href='/admin/admin-login'>Admin Login</a></li>"
            "<li><a href='/chat'>User Chat</a></li>"
            "<li><a href='/about'>About</a></li>"
            "<li><a href='/contact'>Contact</a></li>"
            "</ul>",
            200,
        )

    @app.route("/_routes")
    def _routes():
        return "<br>".join(f"{rule.endpoint} -> {rule}" for rule in app.url_map.iter_rules())

    @app.route("/about")
    def about():
        tpl = os.path.join(app.template_folder or "templates", "shared", "about.html")
        if os.path.exists(tpl):
            return render_template("shared/about.html")
        return "<h1>About Tourist Transport</h1><p>This is the Tourist Transport System.</p>", 200

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        tpl = os.path.join(app.template_folder or "templates", "shared", "contact.html")
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            email = (request.form.get("email") or "").strip()
            subject = (request.form.get("subject") or "").strip()
            message = (request.form.get("message") or "").strip()
            if not (name and email and message):
                flash("Name, email and message are required.", "warning")
                return redirect(url_for("contact"))
            try:
                from db import db_cursor  # type: ignore
                if db_cursor:
                    with db_cursor() as (conn, cur):
                        cur.execute(
                            "INSERT INTO contact_messages (name, email, subject, message, created_at) VALUES (%s,%s,%s,%s,%s)",
                            (name, email, subject, message, datetime.utcnow()),
                        )
                        if conn:
                            conn.commit()
            except Exception:
                current_app.logger.exception("contact save failed")
                flash("Could not send message. Try again later.", "danger")
                return redirect(url_for("contact"))
            flash("Message sent. We'll get back to you.", "success")
            return redirect(url_for("contact"))
        if os.path.exists(tpl):
            return render_template("shared/contact.html")
        return "Contact page (template missing)", 200

    # -----------------------------
    # TEST EMAIL (replaced)
    # -----------------------------
    @app.route("/test-email", methods=["GET", "POST"])
    def test_email():
        """
        Lightweight email smoke-test.

        - Works with GET (querystring) or POST (JSON).
        - Uses async sender.
        - Respects EMAIL_ENABLED (returns 'skipped' when False).
        """
        from utils.email_service import send_email_async

        if request.method == "POST":
            data = request.get_json(force=True, silent=True) or {}
            to = data.get("to")
            subject = data.get("subject")
            text_body = data.get("text_body")
            html_body = data.get("html_body")
        else:
            to = request.args.get("to")
            subject = request.args.get("subject")
            text_body = request.args.get("text_body")
            html_body = request.args.get("html_body")

        to = to or current_app.config.get("MAIL_FROM_EMAIL")
        subject = subject or "Tourist Transport — Test Email"
        text_body = text_body or "This is a test email from Tourist Transport."
        html_body = html_body or "<p><strong>This is a test email</strong> from Tourist Transport.</p>"

        res = send_email_async(
            to_email=to,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        current_app.logger.info("Test email result: %s", res)

        status = 200 if (res.get("ok") or res.get("skipped")) else 500
        return jsonify(res), status

    # Legacy aliases mapping
    with app.app_context():
        aliases = {
            "search": "user.search_places",
            "change_password": "user.user_change_password",  # only if defined in user blueprint
            "logout": "user.logout",
            "user_reviews": "user.user_reviews",
            "admin_login": "admin.admin_login",
        }
        for old, new in aliases.items():
            if new in app.view_functions and old not in app.view_functions:
                app.view_functions[old] = app.view_functions[new]

    return app
# ------------------------------------------------------------
# Shared Socket.IO extension & DB/chat helpers
# ------------------------------------------------------------
try:
    from extensions import socketio as shared_socketio  # type: ignore
except Exception:
    logger.exception("Failed to import extensions.socketio")
    shared_socketio = None  # type: ignore

try:
    from db import db_cursor  # type: ignore
except Exception:
    db_cursor = None
    logger.warning("db.db_cursor not available")


# ------------------------------------------------------------
# SocketIO handler registration
# ------------------------------------------------------------
def register_socket_handlers(sio, app):
    """
    Wire up all Socket.IO events for realtime chat.

    Assumptions:
      - A global/importable `db_cursor` context manager is available.
      - Rooms are named "user_<id>_admin".
      - Flask session has role in {"user","admin"} when available.
    """
    from flask_socketio import join_room, leave_room, emit
    from flask import request as flask_request, session
    from datetime import datetime, timezone
    import pytz

    IST = pytz.timezone("Asia/Kolkata")

    def _format_ist_12h(dt_utc):
        try:
            # ensure aware UTC
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_ist = dt_utc.astimezone(IST)
            return dt_ist.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            return dt_utc.isoformat()

    def _utc_iso_z():
        now = datetime.now(timezone.utc)
        return now, now.isoformat(timespec="seconds").replace("+00:00", "Z")

    def _save_chat(room, sender_type, sender_id, receiver_type, receiver_id, message):
        """Persist chat row and return payload dict with timestamp + display string."""
        now_dt, now_iso = _utc_iso_z()
        new_id = None
        try:
            if db_cursor:
                with db_cursor() as (conn, cur):
                    cur.execute(
                        """
                        INSERT INTO chat (room, sender_type, sender_id, receiver_type, receiver_id, message, timestamp)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (room, sender_type, sender_id, receiver_type, receiver_id, message, now_dt),
                    )
                    if conn:
                        conn.commit()
                    try:
                        new_id = getattr(cur, "lastrowid", None)
                    except Exception:
                        new_id = None
        except Exception:
            app.logger.exception("DB insert failed in _save_chat")

        return {
            "id": new_id,
            "room": room,
            "sender_type": sender_type,
            "sender_id": sender_id,
            "receiver_type": receiver_type,
            "receiver_id": receiver_id,
            "message": message,
            "timestamp": now_iso,                   # UTC ISO with Z
            "timestamp_display": _format_ist_12h(now_dt),  # IST pretty string
        }

    @sio.on("connect")
    def _on_connect():
        app.logger.info(
            "Socket connected: sid=%s role=%s uid=%s aid=%s",
            flask_request.sid, session.get("role"),
            session.get("user_id"), session.get("admin_id")
        )
        emit("connected", {"sid": flask_request.sid, "role": session.get("role")})

    @sio.on("disconnect")
    def _on_disconnect():
        app.logger.info("Socket disconnected: sid=%s", flask_request.sid)

    # Accept BOTH event names: 'join_room' and legacy 'join'
    def _do_join(data):
        room = (data or {}).get("room")
        if not room:
            return
        try:
            join_room(room)
            emit("joined", {"room": room, "sid": flask_request.sid})
            app.logger.info("SID %s joined room %s (role=%s)", flask_request.sid, room, session.get("role"))
        except Exception:
            app.logger.exception("join handler failed")

    @sio.on("join_room")
    def _on_join_room(data):
        _do_join(data)

    @sio.on("join")
    def _on_join_legacy(data):
        _do_join(data)

    @sio.on("leave")
    def _on_leave(data):
        room = (data or {}).get("room")
        if not room:
            return
        try:
            leave_room(room)
            app.logger.info("SID %s left room %s", flask_request.sid, room)
        except Exception:
            app.logger.exception("leave handler failed")

    @sio.on("send_message")
    def _on_send_message(data):
        """
        Expected payload: { room: "user_<id>_admin", message: "..." }
        """
        if not data:
            return
        room = (data.get("room") or "").strip()
        message_text = (data.get("message") or "").strip()
        if not room or not message_text:
            return

        role = session.get("role")
        user_id = session.get("user_id")
        admin_id = session.get("admin_id")

        # Determine sender/receiver
        if role == "admin":
            sender_type = "admin"
            sender_id = admin_id
            sender_name = session.get("username") or "Admin"
            receiver_type = "user"
            try:
                parts = room.split("_")
                receiver_id = int(parts[1]) if len(parts) >= 3 else None
            except Exception:
                receiver_id = None
        elif role == "user":
            sender_type = "user"
            sender_id = user_id
            sender_name = session.get("username") or "You"
            receiver_type = "admin"
            # Non-null admin id for DB integrity
            try:
                receiver_id = int(app.config.get("DEFAULT_ADMIN_ID", 1))
            except Exception:
                receiver_id = 1
        else:
            app.logger.warning("send_message with unknown role; session=%s", dict(session))
            emit("error", {"error": "unauthorized"})
            return

        if sender_id is None:
            app.logger.warning("send_message missing sender_id; role=%s session=%s", role, dict(session))
            emit("error", {"error": "missing sender id"})
            return

        # Persist & broadcast
        msg = _save_chat(room, sender_type, sender_id, receiver_type, receiver_id, message_text)
        msg["sender_name"] = sender_name

        try:
            # broadcast to main room (echo to self too)
            emit("new_message", msg, room=room, include_self=True)

            # Fanout to alternate room names for BOTH directions
            # Some clients may be listening on "user_<id>" instead of "user_<id>_admin".
            alt_targets = set()
            try:
                parts = room.split("_")
                uid = int(parts[1]) if len(parts) >= 3 and parts[0] == "user" else None
            except Exception:
                uid = None

            if uid:
                alt_targets.add(f"user_{uid}")
                alt_targets.add(f"user_{uid}_admin")

            for alt in alt_targets:
                if alt != room:
                    emit("new_message", msg, room=alt)
        except Exception:
            app.logger.exception("emit failed in _on_send_message")


# ------------------------------------------------------------
# Dev tracebacks (optional)  <-- defined BEFORE main
# ------------------------------------------------------------
def enable_dev_tracebacks(app):
    import traceback
    @app.errorhandler(500)
    def handle_internal_error(e):
        tb = traceback.format_exc()
        logger.exception("Internal Server Error: %s\n%s", e, tb)
        return f"<pre>Internal Server Error:\n{e}\n\nTraceback:\n{tb}</pre>", 500
# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    if app.config.get("DEBUG", False):
        enable_dev_tracebacks(app)

    enable_socketio = bool(getattr(config, "ENABLE_SOCKETIO", True))

    if enable_socketio and shared_socketio:
        try:
            if use_eventlet:
                logger.info("Initializing SocketIO with eventlet async_mode")
                shared_socketio.init_app(
                    app,
                    cors_allowed_origins="*",
                    async_mode="eventlet",
                    logger=True,
                    engineio_logger=True,
                    manage_session=True,
                )
            elif use_gevent:
                logger.info("Initializing SocketIO with gevent async_mode")
                shared_socketio.init_app(
                    app,
                    cors_allowed_origins="*",
                    async_mode="gevent",
                    logger=True,
                    engineio_logger=True,
                    manage_session=True,
                )
            else:
                logger.info("Initializing SocketIO without explicit async_mode (threading)")
                shared_socketio.init_app(
                    app,
                    cors_allowed_origins="*",
                    logger=True,
                    engineio_logger=True,
                    manage_session=True,
                )

            register_socket_handlers(shared_socketio, app)

            host = os.environ.get("HOST", "0.0.0.0")
            port = int(os.environ.get("PORT", 5000))
            logger.info("Starting SocketIO server on %s:%s", host, port)
            shared_socketio.run(
                app,
                debug=app.config.get("DEBUG", False),
                use_reloader=False,
                host=host,
                port=port,
            )
        except Exception:
            logger.exception("SocketIO startup failed; fallback to Flask app.run()")
            app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
    else:
        app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
