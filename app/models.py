from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    @classmethod
    def create(cls, username, password):
        return cls(username=username, password_hash=generate_password_hash(password))

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="Estética")
    description = db.Column(db.Text, nullable=False, default="")
    image_url = db.Column(db.String(500), nullable=False, default="")
    half_day_price = db.Column(db.Integer, nullable=False, default=0)
    full_day_price = db.Column(db.Integer, nullable=False, default=0)
    half_day_hours = db.Column(db.Float, nullable=False, default=4)
    full_day_hours = db.Column(db.Float, nullable=False, default=8)
    active = db.Column(db.Boolean, nullable=False, default=True)
    bookings = db.relationship("Booking", backref="machine", lazy=True)
    journeys = db.relationship(
        "RentalJourney",
        backref="machine",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="RentalJourney.id",
    )


class RentalJourney(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    duration_hours = db.Column(db.Float, nullable=False)
    price = db.Column(db.Integer, nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=False)
    journey_type = db.Column(db.String(20), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_hours = db.Column(db.Float, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(160), nullable=False)
    customer_email = db.Column(db.String(160), nullable=False)
    customer_phone = db.Column(db.String(60), nullable=False)
    business_name = db.Column(db.String(160), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="Pendiente")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SiteSetting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")