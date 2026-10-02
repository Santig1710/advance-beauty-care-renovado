from datetime import datetime, time, timedelta
from functools import wraps
from urllib.parse import quote

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.models import AdminUser, Booking, Machine, RentalJourney, SiteSetting

bp = Blueprint("main", __name__)


def setting(key, default=""):
    item = db.session.get(SiteSetting, key)
    return item.value if item else default


def site_content():
    return {item.key: item.value for item in SiteSetting.query.all()}


def journey_rows_for(machine):
    if machine.journeys:
        return [(item.name, item.duration_hours, item.price) for item in machine.journeys]
    return [("Media jornada", 4, 0), ("Jornada completa", 8, 0)]


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("main.admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def available_slots(machine, selected_date, journey):
    duration = journey.duration_hours
    try:
        opening = int(setting("opening_hour", "9"))
        closing = int(setting("closing_hour", "20"))
    except ValueError:
        opening, closing = 9, 20
    if duration <= 0 or opening < 0 or closing > 24 or opening >= closing:
        return []

    day_start = datetime.combine(selected_date, time.min)
    day_end = day_start + timedelta(days=1)
    active_bookings = Booking.query.filter(
        Booking.machine_id == machine.id,
        Booking.status != "Cancelada",
        Booking.start_at < day_end,
    ).all()
    if any(
        booking.start_at + timedelta(hours=booking.duration_hours) > day_start
        for booking in active_bookings
    ):
        return []
    slots = []
    cursor = datetime.combine(selected_date, time(hour=opening))
    closing_at = day_end if closing == 24 else datetime.combine(selected_date, time(hour=closing))
    duration_delta = timedelta(hours=duration)
    while cursor + duration_delta <= closing_at:
        end_at = cursor + duration_delta
        is_past = selected_date == datetime.today().date() and cursor <= datetime.now()
        if not is_past:
            slots.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=30)
    return slots


@bp.app_context_processor
def inject_site_content():
    return {"site": site_content()}


@bp.route("/")
def home():
    machines = Machine.query.filter_by(active=True).order_by(Machine.name).all()
    return render_template("home.html", machines=machines)


@bp.get("/api/availability")
def availability():
    machine = db.session.get(Machine, request.args.get("machine_id", type=int))
    selected_date = request.args.get("date", "")
    journey = db.session.get(RentalJourney, request.args.get("journey_id", type=int))
    if not machine or not machine.active or not journey or journey.machine_id != machine.id:
        return jsonify({"slots": [], "error": "Selección no válida."}), 400
    try:
        booking_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": [], "error": "Fecha no válida."}), 400
    if booking_date < datetime.today().date():
        return jsonify({"slots": []})
    return jsonify({"slots": available_slots(machine, booking_date, journey)})


@bp.post("/reservas")
def create_booking():
    machine = db.session.get(Machine, request.form.get("machine_id", type=int))
    journey = db.session.get(RentalJourney, request.form.get("journey_id", type=int))
    name = request.form.get("customer_name", "").strip()
    email = request.form.get("customer_email", "").strip()
    phone = request.form.get("customer_phone", "").strip()
    if not machine or not machine.active or not journey or journey.machine_id != machine.id:
        abort(400, "La selección de equipo o jornada no es válida.")
    if not name or not email or not phone:
        abort(400, "Completá nombre, correo y teléfono.")
    try:
        booking_date = datetime.strptime(request.form.get("date", ""), "%Y-%m-%d").date()
        start_at = datetime.combine(
            booking_date,
            datetime.strptime(request.form.get("time", ""), "%H:%M").time(),
        )
    except ValueError:
        abort(400, "La fecha o el horario no son válidos.")
    if booking_date < datetime.today().date() or request.form.get("time") not in available_slots(machine, booking_date, journey):
        abort(409, "Ese horario ya no está disponible. Volvé a elegir otro.")

    booking = Booking(
        machine=machine,
        journey_type=journey.name,
        start_at=start_at,
        duration_hours=journey.duration_hours,
        price=journey.price,
        customer_name=name,
        customer_email=email,
        customer_phone=phone,
        business_name=request.form.get("business_name", "").strip(),
        notes=request.form.get("notes", "").strip(),
    )
    db.session.add(booking)
    db.session.commit()

    message = setting("whatsapp_template").format(
        machine=machine.name,
        journey=booking.journey_type,
        date=start_at.strftime("%d/%m/%Y"),
        time=start_at.strftime("%H:%M"),
        name=name,
        phone=phone,
        email=email,
        business=booking.business_name or "No indicado",
        price=f"${booking.price:,}".replace(",", "."),
        notes=booking.notes or "Sin comentarios",
    )
    whatsapp = "https://wa.me/{}?text={}".format(
        "".join(character for character in setting("whatsapp_number") if character.isdigit()),
        quote(message),
    )
    return redirect(whatsapp)


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = AdminUser.query.filter_by(username=request.form.get("username", "")).first()
        if user and user.verify_password(request.form.get("password", "")):
            session.clear()
            session["admin_id"] = user.id
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("main.admin_dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("admin_login.html")


@bp.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("main.home"))


@bp.get("/admin")
@admin_required
def admin_dashboard():
    bookings = Booking.query.order_by(Booking.start_at.desc()).all()
    return render_template("admin_dashboard_configurable.html", machines=Machine.query.order_by(Machine.name).all(), bookings=bookings)


@bp.route("/admin/maquinas/nueva", methods=["GET", "POST"])
@bp.route("/admin/maquinas/<int:machine_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_machine(machine_id=None):
    machine = db.session.get(Machine, machine_id) if machine_id else Machine()
    if machine_id and not machine:
        abort(404)
    if request.method == "POST":
        try:
            machine.name = request.form.get("name", "").strip()
            machine.category = request.form.get("category", "Estética").strip()
            machine.description = request.form.get("description", "").strip()
            machine.image_url = request.form.get("image_url", "").strip()
            machine.active = request.form.get("active") == "on"
            journey_names = request.form.getlist("journey_name")
            journey_hours = request.form.getlist("journey_hours")
            journey_prices = request.form.getlist("journey_price")
            journeys = [
                (name.strip(), float(hours), int(price))
                for name, hours, price in zip(journey_names, journey_hours, journey_prices)
                if name.strip()
            ]
            if not machine.name or not journeys or any(hours <= 0 or price < 0 for _, hours, price in journeys):
                raise ValueError
        except ValueError:
            flash("Revisá los datos y usá duraciones y precios válidos.", "error")
            journey_rows = list(
                zip(
                    request.form.getlist("journey_name"),
                    request.form.getlist("journey_hours"),
                    request.form.getlist("journey_price"),
                )
            ) or journey_rows_for(machine)
            return render_template("machine_form_configurable.html", machine=machine, journey_rows=journey_rows)
        machine.half_day_hours = journeys[0][1]
        machine.half_day_price = journeys[0][2]
        machine.full_day_hours = journeys[1][1] if len(journeys) > 1 else 0
        machine.full_day_price = journeys[1][2] if len(journeys) > 1 else 0
        machine.journeys.clear()
        machine.journeys.extend(
            RentalJourney(name=name, duration_hours=hours, price=price)
            for name, hours, price in journeys
        )
        db.session.add(machine)
        db.session.commit()
        flash("Equipo guardado.", "success")
        return redirect(url_for("main.admin_dashboard"))
    return render_template("machine_form_configurable.html", machine=machine, journey_rows=journey_rows_for(machine))


@bp.post("/admin/maquinas/<int:machine_id>/eliminar")
@admin_required
def delete_machine(machine_id):
    machine = db.session.get(Machine, machine_id)
    if not machine:
        abort(404)
    if machine.bookings:
        machine.active = False
        flash("El equipo tiene reservas vinculadas y se archivó.", "success")
    else:
        db.session.delete(machine)
        flash("Equipo eliminado.", "success")
    db.session.commit()
    return redirect(url_for("main.admin_dashboard"))


@bp.post("/admin/reservas/<int:booking_id>/estado")
@admin_required
def update_booking_status(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        abort(404)
    status = request.form.get("status")
    if status not in {"Pendiente", "Confirmada", "Cancelada"}:
        abort(400)
    booking.status = status
    db.session.commit()
    flash("Estado de la reserva actualizado.", "success")
    return redirect(url_for("main.admin_dashboard") + "#reservas")


@bp.route("/admin/personalizacion", methods=["GET", "POST"])
@admin_required
def edit_content():
    keys = ["hero_title", "hero_subtitle", "hero_images", "whatsapp_number", "whatsapp_template", "opening_hour", "closing_hour"]
    if request.method == "POST":
        opening = request.form.get("opening_hour", "9")
        closing = request.form.get("closing_hour", "20")
        if not opening.isdigit() or not closing.isdigit() or int(opening) >= int(closing) or int(closing) > 24:
            flash("El horario de atención debe ser válido.", "error")
            return render_template("settings.html", settings=site_content())
        for key in keys:
            item = db.session.get(SiteSetting, key)
            if item:
                item.value = request.form.get(key, "").strip()
            else:
                db.session.add(SiteSetting(key=key, value=request.form.get(key, "").strip()))
        db.session.commit()
        flash("Contenido actualizado.", "success")
        return redirect(url_for("main.edit_content"))
    return render_template("settings.html", settings=site_content())