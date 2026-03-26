from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed = db.Column(db.Boolean, default=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=True)
    to_email = db.Column(db.String(255))
    subject = db.Column(db.String(255))
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ... your Booking, EmailLog classes (keep unchanged) ...

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("places.id"), nullable=False)

    # 1 = bad, 2 = average, 3 = good
    category = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(150))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Use backref so we don't require User or Place to explicitly declare `reviews`
    user = db.relationship("User", backref=db.backref("reviews", lazy="dynamic"), lazy="joined")
    place = db.relationship("Place", backref=db.backref("reviews", lazy="dynamic"), lazy="joined")

