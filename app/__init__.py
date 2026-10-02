import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Configuración de base de datos para Render / Local
    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{Path(app.instance_path) / 'advance_beauty.db'}")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-before-deploy"),
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        UPLOAD_FOLDER=str(Path(app.static_folder) / "uploads"),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "Aniadv"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "Sofia2004"),
        WHATSAPP_NUMBER=os.environ.get("WHATSAPP_NUMBER", ""),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from app.routes import PUBLIC_TEXT_FIELDS, bp

    app.register_blueprint(bp)

    with app.app_context():
        from app.models import AdminUser, Machine, RentalJourney, SiteSetting

        db.create_all()
        admin = AdminUser.query.filter_by(username=app.config["ADMIN_USERNAME"]).first()
        if not admin:
            admin = AdminUser.query.order_by(AdminUser.id).first()
            if admin:
                admin.username = app.config["ADMIN_USERNAME"]
                admin.password_hash = AdminUser.create(
                    username=app.config["ADMIN_USERNAME"],
                    password=app.config["ADMIN_PASSWORD"],
                ).password_hash
        if not admin:
            db.session.add(
                AdminUser.create(
                    username=app.config["ADMIN_USERNAME"],
                    password=app.config["ADMIN_PASSWORD"],
                )
            )
        defaults = {
            "hero_title": "Tecnología que transforma.",
            "hero_subtitle": "Aparatología estética premium, en el momento que tu negocio la necesita.",
            "hero_images": "",
            "whatsapp_number": app.config["WHATSAPP_NUMBER"],
            "whatsapp_template": "Hola, quiero consultar por mi reserva:\n\nEquipo: {machine}\nJornada: {journey}\nFecha: {date}\nHorario: {time}\nNombre: {name}\nTeléfono: {phone}",
            "opening_hour": "9",
            "closing_hour": "20",
            "slot_interval": "30",
        }
        defaults.update({key: value for key, (_, value) in PUBLIC_TEXT_FIELDS.items()})
        for key, value in defaults.items():
            if not SiteSetting.query.filter_by(key=key).first():
                db.session.add(SiteSetting(key=key, value=value))
        if Machine.query.count() == 0:
            db.session.add_all(
                [
                    Machine(
                        name="Indiba",
                        category="Radiofrecuencia",
                        description="Tecnología de radiofrecuencia para tratamientos faciales y corporales.",
                        image_url="",
                        half_day_price=85000,
                        full_day_price=145000,
                        half_day_hours=4,
                        full_day_hours=8,
                    ),
                    Machine(
                        name="HIFU",
                        category="Ultrasonido focalizado",
                        description="Ultrasonido focalizado de alta intensidad para protocolos avanzados.",
                        image_url="",
                        half_day_price=110000,
                        full_day_price=185000,
                        half_day_hours=4,
                        full_day_hours=8,
                    ),
                ]
            )
        if not SiteSetting.query.filter_by(key="journeys_migrated_v1").first():
            for machine in Machine.query.all():
                if not machine.journeys:
                    db.session.add_all(
                        [
                            RentalJourney(
                                machine=machine,
                                name="Media jornada",
                                duration_hours=machine.half_day_hours,
                                price=machine.half_day_price,
                            ),
                            RentalJourney(
                                machine=machine,
                                name="Jornada completa",
                                duration_hours=machine.full_day_hours,
                                price=machine.full_day_price,
                            ),
                        ]
                    )
            db.session.add(SiteSetting(key="journeys_migrated_v1", value="1"))
        db.session.commit()

    return app