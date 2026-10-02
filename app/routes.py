import json
import math
import os
from pathlib import Path
from datetime import datetime, time, timedelta
from functools import wraps
from urllib.parse import quote
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.models import AdminUser, Booking, Machine, RentalJourney, SiteSetting

bp = Blueprint("main", __name__)

PUBLIC_TEXT_FIELDS = {
    "text_page_title": ("Título del navegador", "Alquiler de aparatología premium | Advance Beauty Care"),
    "text_brand": ("Nombre del negocio", "Advance Beauty Care"),
    "text_nav_catalog": ("Navegación: catálogo", "Equipos"),
    "text_nav_reserve": ("Navegación: reservar", "Reservar"),
    "text_hero_kicker": ("Portada: texto pequeño", "Tecnología estética · Alquiler profesional"),
    "text_hero_cta": ("Portada: botón", "Explorar equipos"),
    "text_slider_label": ("Portada: descripción accesible de imágenes", "Mostrar imagen"),
    "text_catalog_eyebrow": ("Catálogo: texto pequeño", "Selección profesional"),
    "text_catalog_title": ("Catálogo: título", "Equipos disponibles"),
    "text_catalog_copy": ("Catálogo: descripción", "Elegí tu tecnología y armá una reserva en pocos pasos."),
    "text_search_placeholder": ("Buscador: indicación", "Buscar por equipo o tratamiento"),
    "text_search_aria": ("Buscador: descripción accesible", "Buscar equipos"),
    "text_filter_all": ("Filtro: todas las categorías", "Todos"),
    "text_product_badge": ("Etiqueta de producto", "Premium"),
    "text_price_from": ("Precio: desde", "Desde"),
    "text_availability_consult": ("Precio: sin jornadas", "Consultar disponibilidad"),
    "text_choose_equipment": ("Botón de equipo", "Elegir"),
    "text_no_journeys": ("Equipo sin jornadas configuradas", "Este equipo no tiene jornadas configuradas"),
    "text_no_equipment": ("Catálogo vacío", "Pronto vas a encontrar nuevos equipos disponibles."),
    "text_no_search_result": ("Búsqueda sin resultados", "No encontramos equipos con esa búsqueda."),
    "text_feature_1_title": ("Paso 1: título", "Elegí"),
    "text_feature_1_copy": ("Paso 1: descripción", "Tecnología para cada protocolo"),
    "text_feature_2_title": ("Paso 2: título", "Reservá"),
    "text_feature_2_copy": ("Paso 2: descripción", "Turno confirmado sin llamadas"),
    "text_feature_3_title": ("Paso 3: título", "Potenciá"),
    "text_feature_3_copy": ("Paso 3: descripción", "Tu práctica profesional"),
    "text_footer_copy": ("Pie de página: descripción", "Aparatología estética de alta gama"),
    "text_booking_badge": ("Reserva: texto pequeño", "Tu reserva"),
    "text_booking_title": ("Reserva: título", "Un paso más cerca"),
    "text_progress_1": ("Reserva: paso 1", "Jornada"),
    "text_progress_2": ("Reserva: paso 2", "Turno"),
    "text_progress_3": ("Reserva: paso 3", "Tus datos"),
    "text_journey_title": ("Reserva: elegir jornada", "¿Qué jornada necesitás?"),
    "text_journey_copy": ("Reserva: ayuda para jornada", "Seleccioná la duración que mejor se adapta a tu agenda."),
    "text_journey_continue": ("Reserva: continuar sin jornada", "Elegí una jornada para continuar"),
    "text_continue": ("Reserva: botón continuar", "Continuar"),
    "text_date_title": ("Reserva: elegir fecha", "Elegí fecha y horario"),
    "text_date_copy": ("Reserva: ayuda para fecha", "Los turnos se actualizan según la disponibilidad real."),
    "text_date_label": ("Reserva: campo fecha", "Fecha"),
    "text_slot_label": ("Reserva: horarios disponibles", "Horarios disponibles"),
    "text_slot_loading": ("Reserva: consultando horarios", "Consultando..."),
    "text_slot_empty": ("Reserva: sin horarios", "No hay horarios libres para esta fecha. Probá otra."),
    "text_back": ("Reserva: botón atrás", "Atrás"),
    "text_contact_title": ("Reserva: datos de contacto", "Tus datos de contacto"),
    "text_contact_copy": ("Reserva: ayuda de contacto", "Los usamos para preparar tu reserva y contactarte."),
    "text_hours_of_use": ("Reserva: duración de jornada", "horas de uso"),
    "text_customer_name": ("Reserva: nombre", "Nombre y apellido"),
    "text_customer_email": ("Reserva: correo", "Correo electrónico"),
    "text_customer_phone": ("Reserva: teléfono", "Teléfono / WhatsApp"),
    "text_business_name": ("Reserva: negocio", "Nombre del centro"),
    "text_optional": ("Reserva: marca de campo opcional", "(opcional)"),
    "text_notes": ("Reserva: comentarios", "Comentarios"),
    "text_booking_summary": ("Reserva: confirmación", "Al confirmar guardamos tu solicitud y abrimos WhatsApp con los detalles."),
    "text_confirm_booking": ("Reserva: botón confirmar", "Confirmar por WhatsApp"),
    "text_close_booking": ("Reserva: descripción accesible para cerrar", "Cerrar reserva"),
    "text_slot_error": ("Reserva: error al consultar horarios", "No pudimos consultar los turnos. Probá nuevamente."),
    "text_delivery_address": ("Reserva: dirección del centro", "Dirección del centro de estética"),
    "text_delivery_pending": ("Reserva: aviso de envío pendiente", "Envío y total final a confirmar"),
    "text_operator_option": ("Reserva: opción de operadora", "Quiero alquilar con operadora"),
    "text_rental_amount": ("Reserva: detalle de alquiler", "Alquiler"),
    "text_operator_amount": ("Reserva: detalle de operadora", "Operadora"),
    "text_subtotal_without_shipping": ("Reserva: subtotal sin envío", "Subtotal sin envío"),
}

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024
IMAGE_SIGNATURES = {
    ".jpg": lambda header: header.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda header: header.startswith(b"\xff\xd8\xff"),
    ".png": lambda header: header.startswith(b"\x89PNG\r\n\x1a\n"),
    ".gif": lambda header: header.startswith((b"GIF87a", b"GIF89a")),
    ".webp": lambda header: header.startswith(b"RIFF") and header[8:12] == b"WEBP",
}
def setting(key, default=""):
    item = db.session.get(SiteSetting, key)
    return item.value if item else default


def site_content():
    return {item.key: item.value for item in SiteSetting.query.all()}


def is_local_upload(value):
    if not value or not value.startswith("/static/uploads/"):
        return False
    filename = value.removeprefix("/static/uploads/")
    return bool(filename) and Path(filename).name == filename


def validate_image_upload(image):
    if not image or not image.filename:
        return
    extension = Path(image.filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Usá una imagen JPG, PNG, WEBP o GIF.")
    image.stream.seek(0, os.SEEK_END)
    size = image.stream.tell()
    image.stream.seek(0)
    if size > MAX_IMAGE_SIZE:
        raise ValueError("Cada imagen debe pesar menos de 8 MB.")
    header = image.stream.read(12)
    image.stream.seek(0)
    if not IMAGE_SIGNATURES[extension](header):
        raise ValueError("El archivo seleccionado no parece una imagen válida.")


def save_image_upload(image):
    validate_image_upload(image)
    extension = Path(image.filename).suffix.lower()
    filename = f"{uuid4().hex}{extension}"
    upload_directory = Path(current_app.config["UPLOAD_FOLDER"])
    upload_directory.mkdir(parents=True, exist_ok=True)
    image.save(upload_directory / filename)
    return f"/static/uploads/{filename}"


def settings_context():
    values = site_content()
    sections = []
    try:
        parsed = json.loads(values.get("custom_sections", "[]"))
        if isinstance(parsed, list):
            sections = [item for item in parsed if isinstance(item, dict)]
    except (TypeError, json.JSONDecodeError):
        pass
    return {
        "settings": values,
        "public_text_fields": [
            {"key": key, "label": label, "value": values.get(key, default)}
            for key, (label, default) in PUBLIC_TEXT_FIELDS.items()
        ],
        "hero_images": [image for image in values.get("hero_images", "").splitlines() if is_local_upload(image)],
        "custom_sections": sections,
    }


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
        interval = int(setting("slot_interval", "30"))
    except ValueError:
        opening, closing = 9, 20
        interval = 30
    if duration <= 0 or opening < 0 or closing > 24 or opening >= closing or interval <= 0:
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
        cursor += timedelta(minutes=interval)
    return slots


@bp.app_context_processor
def inject_site_content():
    return {"site": site_content()}


@bp.route("/")
def home():
    machines = Machine.query.filter_by(active=True).order_by(Machine.name).all()
    settings = site_content()
    hero_images = [image for image in settings.get("hero_images", "").splitlines() if is_local_upload(image)]
    machine_images = {
        machine.id: machine.image_url if is_local_upload(machine.image_url) else ""
        for machine in machines
    }
    try:
        custom_sections = json.loads(settings.get("custom_sections", "[]"))
        if not isinstance(custom_sections, list):
            custom_sections = []
    except (TypeError, json.JSONDecodeError):
        custom_sections = []
    try:
        operator_price = max(0, int(settings.get("operator_price", "0")))
    except ValueError:
        operator_price = 0
    try:
        price_per_km = max(0, int(settings.get("shipping_per_km", "1000")))
    except ValueError:
        price_per_km = 1000
    shipping_message = settings.get(
        "shipping_message",
        "El envío se cobra a partir de {km_incluidos} km desde la ubicación de la máquina: {precio_km} por cada km adicional.",
    )
    shipping_message = shipping_message.replace("{precio_km}", f"${price_per_km:,}".replace(",", "."))
    shipping_message = shipping_message.replace("{km_incluidos}", str(settings.get("shipping_free_km", "10")))
    return render_template(
        "home.html",
        machines=machines,
        machine_images=machine_images,
        hero_images=hero_images,
        custom_sections=custom_sections,
        operator_price=operator_price,
        shipping_message=shipping_message,
    )


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

    address = request.form.get("delivery_address", "").strip()
    if not address or len(address) > 300:
        abort(400, "Ingresá la dirección del centro de estética (hasta 300 caracteres).")

    with_operator = request.form.get("with_operator") == "on"
    operator_price = int(setting("operator_price", "0"))
    if with_operator and operator_price <= 0:
        abort(400, "La opción con operadora no está disponible actualmente.")
    operator_fee = operator_price if with_operator else 0
    subtotal = journey.price + operator_fee
    total_price = subtotal

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
        delivery_address=address,
        distance_km=0,
        delivery_fee=0,
        with_operator=with_operator,
        operator_fee=operator_fee,
        subtotal=subtotal,
        total_price=total_price,
        notes=request.form.get("notes", "").strip(),
    )
    db.session.add(booking)
    db.session.commit()

    template = setting("whatsapp_template")
    money = lambda amount: f"${amount:,}".replace(",", ".")
    message = template.format(
        machine=machine.name,
        journey=booking.journey_type,
        date=start_at.strftime("%d/%m/%Y"),
        time=start_at.strftime("%H:%M"),
        name=name,
        phone=phone,
        email=email,
        business=booking.business_name or "No indicado",
        price=money(booking.price),
        address=address,
        distance="A confirmar manualmente",
        subtotal=money(subtotal),
        shipping="A confirmar manualmente",
        operator=money(operator_fee) if with_operator else "No",
        total="A confirmar manualmente",
        notes=booking.notes or "Sin comentarios",
    )
    required_breakdown = ("{address}", "{distance}", "{subtotal}", "{shipping}", "{operator}", "{total}")
    if not all(variable in template for variable in required_breakdown):
        message += (
            "\n\nDetalle del pedido:\n"
            f"Dirección: {address}\nDistancia y envío: a confirmar manualmente\n"
            f"Alquiler: {money(booking.price)}\n"
            f"Operadora: {money(operator_fee) if with_operator else 'No'}\n"
            f"Envío: a confirmar manualmente\n"
            f"Subtotal sin envío: {money(subtotal)}\nTotal final: a confirmar"
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
    machines = Machine.query.order_by(Machine.name).all()
    machine_images = {
        machine.id: machine.image_url if is_local_upload(machine.image_url) else ""
        for machine in machines
    }
    return render_template(
        "admin_dashboard_configurable.html",
        machines=machines,
        machine_images=machine_images,
        bookings=bookings,
    )


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
            image_upload = request.files.get("image_file")
            validate_image_upload(image_upload)
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
            flash("Revisá los datos, las duraciones y la imagen seleccionada.", "error")
            journey_rows = list(
                zip(
                    request.form.getlist("journey_name"),
                    request.form.getlist("journey_hours"),
                    request.form.getlist("journey_price"),
                )
            ) or journey_rows_for(machine)
            return render_template("machine_form_configurable.html", machine=machine, journey_rows=journey_rows)
        if image_upload and image_upload.filename:
            machine.image_url = save_image_upload(image_upload)
        elif not is_local_upload(machine.image_url):
            machine.image_url = ""
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
    keys = [
        "hero_title", "hero_subtitle", "whatsapp_number", "whatsapp_template",
        "opening_hour", "closing_hour", "slot_interval",
        "shipping_free_km", "shipping_per_km", "shipping_message", "operator_price",
    ]
    if request.method == "POST":
        opening = request.form.get("opening_hour", "9")
        closing = request.form.get("closing_hour", "20")
        interval = request.form.get("slot_interval", "30")
        free_km = request.form.get("shipping_free_km", "10")
        price_per_km = request.form.get("shipping_per_km", "1000")
        shipping_message = request.form.get("shipping_message", "").strip()
        operator_price = request.form.get("operator_price", "0")
        uploads = request.files.getlist("hero_image_files")
        try:
            if (
                not opening.isdigit()
                or not closing.isdigit()
                or int(opening) >= int(closing)
                or int(opening) > 23
                or int(closing) > 24
                or not interval.isdigit()
                or not 5 <= int(interval) <= 360
                or int(interval) % 5 != 0
                or not math.isfinite(float(free_km))
                or not 0 <= float(free_km) <= 500
                or not price_per_km.isdigit()
                or int(price_per_km) < 0
                or not shipping_message
                or len(shipping_message) > 500
                or not operator_price.isdigit()
                or int(operator_price) < 0
            ):
                raise ValueError
            for image in uploads:
                validate_image_upload(image)
        except ValueError:
            flash("Revisá horarios, tarifas, kilómetros e imágenes.", "error")
            return render_template("settings.html", **settings_context())

        removed_images = set(request.form.getlist("remove_hero_image"))
        hero_images = [
            image
            for image in site_content().get("hero_images", "").splitlines()
            if is_local_upload(image) and image not in removed_images
        ]
        hero_images.extend(save_image_upload(image) for image in uploads if image.filename)
        for key in keys + list(PUBLIC_TEXT_FIELDS):
            item = db.session.get(SiteSetting, key)
            if item:
                item.value = request.form.get(key, "").strip()
            else:
                db.session.add(SiteSetting(key=key, value=request.form.get(key, "").strip()))
        hero_setting = db.session.get(SiteSetting, "hero_images")
        hero_value = "\n".join(hero_images)
        if hero_setting:
            hero_setting.value = hero_value
        else:
            db.session.add(SiteSetting(key="hero_images", value=hero_value))
        custom_sections = [
            {"title": title.strip(), "body": body.strip()}
            for title, body in zip(
                request.form.getlist("custom_section_title"),
                request.form.getlist("custom_section_body"),
            )
            if title.strip() or body.strip()
        ]
        sections_setting = db.session.get(SiteSetting, "custom_sections")
        sections_value = json.dumps(custom_sections, ensure_ascii=False)
        if sections_setting:
            sections_setting.value = sections_value
        else:
            db.session.add(SiteSetting(key="custom_sections", value=sections_value))
        db.session.commit()
        flash("Contenido actualizado.", "success")
        return redirect(url_for("main.edit_content"))
    return render_template("settings.html", **settings_context())