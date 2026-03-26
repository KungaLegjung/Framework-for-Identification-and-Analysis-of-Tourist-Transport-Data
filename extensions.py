# extensions.py
from flask_socketio import SocketIO
import config

# Create a single shared SocketIO instance to be initialized in app.py
socketio = SocketIO(
    async_mode=None,  # let it auto-pick eventlet/gevent/threading
    cors_allowed_origins="*",  # allow all origins (fine for dev; restrict in prod)
    manage_session=True,  # ensures Flask session data is available in socket handlers
    logger=True,          # log Socket.IO events (good for debugging)
    engineio_logger=True, # log Engine.IO events (low-level transport debugging)
    message_queue=getattr(config, "SOCKETIO_MESSAGE_QUEUE", None),  # optional Redis/RabbitMQ
)
