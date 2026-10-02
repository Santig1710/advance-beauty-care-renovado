# Advance Beauty Care

Base web para alquiler de aparatología estética, construida con Flask, SQLite, SQLAlchemy y Tailwind CSS por CDN.

## Estructura

```text
.
├── app/
│   ├── __init__.py          # Configuración, inicialización y datos de ejemplo
│   ├── models.py            # Administrador, equipos, reservas y contenido editable
│   ├── routes.py            # Catálogo, disponibilidad, reservas y panel admin
│   └── templates/
│       ├── base.html
│       ├── home.html
│       ├── admin_login.html
│       ├── admin_dashboard.html
│       ├── machine_form.html
│       └── settings.html
├── instance/                # SQLite se crea aquí al iniciar
├── requirements.txt
├── run.py
└── .env.example
```

## Inicio local

Instalá dependencias con `python -m pip install -r requirements.txt`. En PowerShell, configurá las credenciales y el número del negocio antes de iniciar:

```powershell
$env:SECRET_KEY = "un-secreto-largo-y-aleatorio"
$env:ADMIN_USERNAME = "Aniadv"
$env:ADMIN_PASSWORD = "Sofia2004"
$env:WHATSAPP_NUMBER = "5491112345678"
python run.py
```

Abrí `http://127.0.0.1:5000`; el panel se encuentra en `/admin/login` y no aparece enlazado en la vista de clientes. Las credenciales iniciales son `Aniadv` y `Sofia2004`; la contraseña se guarda como hash. Cambialas antes de publicar la aplicación.

## Alcance del flujo

La portada muestra equipos y un carrusel configurable. La reserva permite elegir jornada, fecha, turno y datos de contacto. La disponibilidad se consulta y valida de nuevo en el servidor al guardar; la solicitud queda como pendiente y el navegador se redirige a WhatsApp. El panel permite crear, editar y eliminar/archivar equipos, actualizar estados de reservas y modificar textos, banners, horarios y plantilla de mensaje.

Cada equipo puede tener una o más jornadas personalizadas, con nombre, duración y precio. Las opciones anteriores se migran al iniciar. Una reserva pendiente o confirmada bloquea el equipo durante todo ese día; las canceladas liberan la fecha. Las imágenes se gestionan mediante URL pública. Para producción, configurá HTTPS, una clave secreta propia, credenciales seguras y protección CSRF/rate limiting antes de exponer los formularios.