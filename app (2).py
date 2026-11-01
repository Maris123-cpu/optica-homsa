import json
import os
import uuid
from datetime import datetime, date, time, timedelta
from functools import wraps

from flask import (Flask, render_template, redirect, url_for,
                   flash, request, abort, jsonify, session)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError

from dotenv import load_dotenv

from models import db, Usuario, Lente, Cita, ResultadoTest, Receta

# Lee las claves secretas del archivo .env (junto a este archivo)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-solo-para-desarrollo-cambiala")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///optima.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("PRODUCCION") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "img", "lentes")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # máximo 3 MB por foto
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ---------- Configuración de citas ----------
HORA_APERTURA = 8            # 8:00 am
HORA_CIERRE = 17             # 5:00 pm
DURACION_CITA = 30           # minutos
DIAS_ATENCION = [0, 1, 2, 3, 4]   # 0=lunes ... 6=domingo. Para incluir sábado: [0,1,2,3,4,5]
DIAS_MAX_ANTICIPACION = 60   # hasta cuántos días adelante se puede agendar
MAX_CITAS_ACTIVAS = 3        # citas activas por cliente
HORAS_MIN_CANCELAR = 2       # el cliente cancela con al menos 2 horas de anticipación

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


@app.template_filter("fecha_larga")
def fecha_larga(valor):
    return f"{DIAS_ES[valor.weekday()].capitalize()} {valor.day} de {MESES_ES[valor.month - 1]} de {valor.year}"


@app.template_filter("hora")
def hora_12(valor):
    return valor.strftime("%I:%M %p").lstrip("0")


db.init_app(app)
csrf = CSRFProtect(app)
def ip_del_cliente():
    """IP real del visitante. En PythonAnywhere llega en la cabecera X-Real-IP."""
    if os.environ.get("PRODUCCION") == "1":
        return request.headers.get("X-Real-IP") or get_remote_address()
    return get_remote_address()


limiter = Limiter(key_func=ip_del_cliente, app=app,
                  default_limits=[], storage_uri="memory://")

# ---------- Sesiones de usuario ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "info"


@login_manager.user_loader
def cargar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))


def solo_doctor(f):
    """Protege una página para que solo la vea el doctor."""
    @wraps(f)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.es_doctor:
            abort(403)
        return f(*args, **kwargs)
    return envoltura


def ir_a_mi_panel():
    if current_user.es_doctor:
        return redirect(url_for("panel_doctor"))
    return redirect(url_for("panel_cliente"))


# ---------- Datos iniciales ----------
def actualizar_esquema():
    """Agrega lo nuevo a una base de datos que ya existe, sin borrar datos."""
    columnas = [fila[1] for fila in db.session.execute(text("PRAGMA table_info(usuarios)"))]
    if "cedula" not in columnas:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN cedula VARCHAR(30)"))
        db.session.commit()

    # Regla: no puede haber dos citas ACTIVAS del mismo doctor a la misma hora
    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_cita_activa "
            "ON citas (doctor_id, fecha_hora) WHERE estado != 'cancelada'"))
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print("Aviso: no se pudo crear la regla de citas únicas:", error)


def crear_datos_iniciales():
    """Crea las tablas y agrega un doctor y lentes de ejemplo."""
    db.create_all()
    actualizar_esquema()

    if not Usuario.query.filter_by(rol="doctor").first():
        en_produccion = os.environ.get("PRODUCCION") == "1"
        clave_doctor = os.environ.get("DOCTOR_PASSWORD")
        if en_produccion and not clave_doctor:
            raise RuntimeError("Falta DOCTOR_PASSWORD en el archivo .env")
        if clave_doctor and len(clave_doctor) < 8:
            raise RuntimeError("DOCTOR_PASSWORD debe tener al menos 8 caracteres")

        doctor = Usuario(
            nombre="Doctor",
            apellidos="Óptica HomSa",
            email=os.environ.get("DOCTOR_EMAIL", "doctor@optimahomsa.com").strip().lower(),
            telefono="0000000000",
            rol="doctor",
        )
        doctor.set_password(clave_doctor or "Doctor123")
        db.session.add(doctor)

    if Lente.query.count() == 0 and os.environ.get("PRODUCCION") != "1":
        ejemplos = [
            Lente(nombre="Clásico Redondo", marca="Ray-Ban", forma="redondo",
                  material="metal", color="dorado", genero="unisex", precio=2400,
                  descripcion="Armazón metálico ligero de estilo clásico."),
            Lente(nombre="Urban Square", marca="Oakley", forma="cuadrado",
                  material="acetato", color="negro", genero="hombre", precio=2900,
                  descripcion="Acetato resistente, ideal para uso diario."),
            Lente(nombre="Cat Eye Elegance", marca="Vogue", forma="cat eye",
                  material="acetato", color="carey", genero="mujer", precio=2200,
                  descripcion="Diseño elegante con terminación ligeramente levantada."),
            Lente(nombre="Aviador Titanio", marca="Carrera", forma="aviador",
                  material="titanio", color="plateado", genero="unisex", precio=3500,
                  descripcion="Titanio ultraligero e hipoalergénico."),
            Lente(nombre="Kids Flex", marca="Nano", forma="redondo",
                  material="silicona", color="azul", genero="niño", precio=1200,
                  descripcion="Flexible y resistente para los más pequeños."),
            Lente(nombre="Office Slim", marca="Tommy Hilfiger", forma="rectangular",
                  material="metal", color="gris", genero="hombre", precio=2700,
                  descripcion="Perfil delgado, perfecto para oficina."),
        ]
        db.session.add_all(ejemplos)

    db.session.commit()


@app.after_request
def cabeceras_de_seguridad(respuesta):
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Las páginas con datos de salud no se guardan en la caché del navegador
    if request.endpoint != "static" and current_user.is_authenticated:
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# ---------- Rutas públicas ----------
@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/registro", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def registro():
    if current_user.is_authenticated:
        return ir_a_mi_panel()

    datos = {}
    if request.method == "POST":
        datos = request.form
        nombre = request.form.get("nombre", "").strip()
        apellidos = request.form.get("apellidos", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        fecha_txt = request.form.get("fecha_nacimiento", "").strip()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")
        acepta = "acepto" in request.form

        if not nombre or not apellidos or not email or not password:
            flash("Completa todos los campos obligatorios.", "error")
        elif len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
        elif password != confirmar:
            flash("Las contraseñas no coinciden.", "error")
        elif not acepta:
            flash("Debes aceptar el aviso de privacidad para registrarte.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("Ese correo ya está registrado.", "error")
        else:
            fecha_nac = None
            if fecha_txt:
                try:
                    fecha_nac = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
                except ValueError:
                    fecha_nac = None

            nuevo = Usuario(nombre=nombre, apellidos=apellidos, email=email,
                            telefono=telefono, fecha_nacimiento=fecha_nac,
                            rol="cliente")
            nuevo.set_password(password)
            db.session.add(nuevo)
            db.session.commit()

            flash("¡Cuenta creada! Ya puedes iniciar sesión.", "exito")
            return redirect(url_for("login"))

    return render_template("registro.html", datos=datos)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return ir_a_mi_panel()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.activo and usuario.check_password(password):
            login_user(usuario)
            session.permanent = True   # la sesión expira a las 2 horas
            flash(f"Bienvenido, {usuario.nombre}.", "exito")
            return ir_a_mi_panel()

        flash("Correo o contraseña incorrectos.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Cerraste sesión correctamente.", "info")
    return redirect(url_for("inicio"))


# ---------- Paneles protegidos ----------
@app.route("/panel")
@login_required
def panel_cliente():
    if current_user.es_doctor:
        return redirect(url_for("panel_doctor"))
    proxima = (Cita.query
               .filter(Cita.cliente_id == current_user.id,
                       Cita.fecha_hora >= datetime.now(),
                       Cita.estado.in_(["pendiente", "confirmada"]))
               .order_by(Cita.fecha_hora).first())
    return render_template("panel_cliente.html", proxima=proxima)


@app.route("/doctor")
@solo_doctor
def panel_doctor():
    inicio_hoy = datetime.combine(date.today(), time(0, 0))
    citas_hoy = (Cita.query
                 .filter(Cita.doctor_id == current_user.id,
                         Cita.fecha_hora >= inicio_hoy,
                         Cita.fecha_hora < inicio_hoy + timedelta(days=1),
                         Cita.estado != "cancelada").count())
    pendientes = (Cita.query
                  .filter(Cita.doctor_id == current_user.id,
                          Cita.estado == "pendiente",
                          Cita.fecha_hora >= datetime.now()).count())
    return render_template("panel_doctor.html",
                           total_clientes=Usuario.query.filter_by(rol="cliente").count(),
                           total_lentes=Lente.query.count(),
                           citas_hoy=citas_hoy, pendientes=pendientes)


# ---------- Funciones de ayuda para el catálogo ----------
def guardar_imagen(archivo):
    """Guarda la foto con un nombre único. Devuelve el nombre o None si no es válida."""
    if not archivo or archivo.filename == "" or "." not in archivo.filename:
        return None
    extension = archivo.filename.rsplit(".", 1)[-1].lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        return None
    nombre = f"{uuid.uuid4().hex}.{extension}"
    archivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nombre))
    return nombre


def borrar_imagen(nombre):
    if nombre:
        ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre)
        if os.path.exists(ruta):
            os.remove(ruta)


def valores_distintos(columna):
    """Lista de valores sin repetir de una columna (para llenar los filtros)."""
    filas = (db.session.query(columna)
             .filter(Lente.disponible == True, columna.isnot(None), columna != "")
             .distinct().all())
    return sorted(fila[0] for fila in filas)


def a_numero(texto):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def valores_de_lente(lente):
    valores = {
        "nombre": lente.nombre, "marca": lente.marca, "forma": lente.forma or "",
        "material": lente.material or "", "color": lente.color or "",
        "genero": lente.genero or "", "precio": lente.precio,
        "descripcion": lente.descripcion or "",
    }
    if lente.disponible:
        valores["disponible"] = "on"
    return valores


def llenar_lente_desde_formulario(lente):
    """Lee el formulario y llena el lente. Devuelve un mensaje de error o None."""
    f = request.form
    nombre = f.get("nombre", "").strip()
    marca = f.get("marca", "").strip()

    if not nombre or not marca:
        return "El nombre y la marca son obligatorios."
    try:
        precio = float(f.get("precio", ""))
    except ValueError:
        return "El precio debe ser un número."
    if precio < 0:
        return "El precio no puede ser negativo."

    archivo = request.files.get("imagen")
    nueva_imagen = None
    if archivo and archivo.filename:
        nueva_imagen = guardar_imagen(archivo)
        if not nueva_imagen:
            return "La imagen debe ser PNG, JPG o WEBP."

    lente.nombre = nombre
    lente.marca = marca
    lente.forma = f.get("forma", "").strip().lower()
    lente.material = f.get("material", "").strip().lower()
    lente.color = f.get("color", "").strip().lower()
    lente.genero = f.get("genero", "").strip().lower()
    lente.precio = precio
    lente.descripcion = f.get("descripcion", "").strip()
    lente.disponible = "disponible" in f

    if nueva_imagen:
        borrar_imagen(lente.imagen)
        lente.imagen = nueva_imagen
    return None


# ---------- Catálogo público ----------
@app.route("/catalogo")
def catalogo():
    q = request.args.get("q", "").strip()
    marca = request.args.get("marca", "")
    forma = request.args.get("forma", "")
    material = request.args.get("material", "")
    genero = request.args.get("genero", "")
    precio_min = request.args.get("precio_min", "")
    precio_max = request.args.get("precio_max", "")
    orden = request.args.get("orden", "recientes")

    consulta = Lente.query.filter_by(disponible=True)

    if q:
        consulta = consulta.filter(or_(Lente.nombre.ilike(f"%{q}%"),
                                       Lente.marca.ilike(f"%{q}%")))
    if marca:
        consulta = consulta.filter(Lente.marca == marca)
    if forma:
        consulta = consulta.filter(Lente.forma == forma)
    if material:
        consulta = consulta.filter(Lente.material == material)
    if genero:
        consulta = consulta.filter(Lente.genero == genero)
    if a_numero(precio_min) is not None:
        consulta = consulta.filter(Lente.precio >= a_numero(precio_min))
    if a_numero(precio_max) is not None:
        consulta = consulta.filter(Lente.precio <= a_numero(precio_max))

    if orden == "precio_asc":
        consulta = consulta.order_by(Lente.precio.asc())
    elif orden == "precio_desc":
        consulta = consulta.order_by(Lente.precio.desc())
    elif orden == "nombre":
        consulta = consulta.order_by(Lente.nombre.asc())
    else:
        consulta = consulta.order_by(Lente.id.desc())

    filtros = {"q": q, "marca": marca, "forma": forma, "material": material,
               "genero": genero, "precio_min": precio_min,
               "precio_max": precio_max, "orden": orden}
    opciones = {"marca": valores_distintos(Lente.marca),
                "forma": valores_distintos(Lente.forma),
                "material": valores_distintos(Lente.material),
                "genero": valores_distintos(Lente.genero)}

    return render_template("catalogo.html", lentes=consulta.all(),
                           filtros=filtros, opciones=opciones)


@app.route("/lente/<int:lente_id>")
def lente_detalle(lente_id):
    lente = db.get_or_404(Lente, lente_id)
    if not lente.disponible and not (current_user.is_authenticated and current_user.es_doctor):
        abort(404)
    parecidos = (Lente.query
                 .filter(Lente.disponible == True, Lente.id != lente.id,
                         or_(Lente.forma == lente.forma, Lente.marca == lente.marca))
                 .limit(3).all())
    return render_template("lente_detalle.html", lente=lente, parecidos=parecidos)


# ---------- Administración del catálogo (solo doctor) ----------
@app.route("/doctor/lentes")
@solo_doctor
def doctor_lentes():
    lentes = Lente.query.order_by(Lente.id.desc()).all()
    return render_template("doctor_lentes.html", lentes=lentes)


@app.route("/doctor/lentes/nuevo", methods=["GET", "POST"])
@solo_doctor
def doctor_lente_nuevo():
    if request.method == "POST":
        lente = Lente(nombre="", marca="", precio=0)
        error = llenar_lente_desde_formulario(lente)
        if error:
            flash(error, "error")
            return render_template("doctor_lente_form.html", lente=None,
                                   valores=request.form)
        db.session.add(lente)
        db.session.commit()
        flash("Lente agregado al catálogo.", "exito")
        return redirect(url_for("doctor_lentes"))
    return render_template("doctor_lente_form.html", lente=None,
                           valores={"disponible": "on"})


@app.route("/doctor/lentes/<int:lente_id>/editar", methods=["GET", "POST"])
@solo_doctor
def doctor_lente_editar(lente_id):
    lente = db.get_or_404(Lente, lente_id)
    if request.method == "POST":
        error = llenar_lente_desde_formulario(lente)
        if error:
            db.session.rollback()
            flash(error, "error")
            return render_template("doctor_lente_form.html", lente=lente,
                                   valores=request.form)
        db.session.commit()
        flash("Cambios guardados.", "exito")
        return redirect(url_for("doctor_lentes"))
    return render_template("doctor_lente_form.html", lente=lente,
                           valores=valores_de_lente(lente))


@app.route("/doctor/lentes/<int:lente_id>/disponibilidad", methods=["POST"])
@solo_doctor
def doctor_lente_disponibilidad(lente_id):
    lente = db.get_or_404(Lente, lente_id)
    lente.disponible = not lente.disponible
    db.session.commit()
    estado = "visible" if lente.disponible else "oculto"
    flash(f"«{lente.nombre}» ahora está {estado} en el catálogo.", "info")
    return redirect(url_for("doctor_lentes"))


@app.route("/doctor/lentes/<int:lente_id>/eliminar", methods=["POST"])
@solo_doctor
def doctor_lente_eliminar(lente_id):
    lente = db.get_or_404(Lente, lente_id)
    borrar_imagen(lente.imagen)
    db.session.delete(lente)
    db.session.commit()
    flash("Lente eliminado.", "info")
    return redirect(url_for("doctor_lentes"))


# ---------- Citas: funciones de ayuda ----------
def horarios_del_dia(fecha, doctor_id):
    """Devuelve las horas LIBRES de un día para un doctor."""
    if fecha.weekday() not in DIAS_ATENCION:
        return []

    inicio = datetime.combine(fecha, time(HORA_APERTURA, 0))
    fin = datetime.combine(fecha, time(HORA_CIERRE, 0))

    citas_del_dia = Cita.query.filter(
        Cita.doctor_id == doctor_id,
        Cita.estado != "cancelada",
        Cita.fecha_hora >= inicio,
        Cita.fecha_hora < fin,
    ).all()
    ocupadas = {c.fecha_hora for c in citas_del_dia}

    libres = []
    actual = inicio
    ahora = datetime.now()
    while actual + timedelta(minutes=DURACION_CITA) <= fin:
        if actual > ahora and actual not in ocupadas:
            libres.append(actual)
        actual += timedelta(minutes=DURACION_CITA)
    return libres


def puede_cancelar(cita):
    faltan = cita.fecha_hora - datetime.now()
    return (cita.estado in ("pendiente", "confirmada")
            and faltan >= timedelta(hours=HORAS_MIN_CANCELAR))


app.jinja_env.globals["puede_cancelar"] = puede_cancelar


# ---------- Citas del cliente ----------
@app.route("/citas")
@login_required
def mis_citas():
    if current_user.es_doctor:
        return redirect(url_for("agenda_doctor"))

    todas = (Cita.query.filter_by(cliente_id=current_user.id)
             .order_by(Cita.fecha_hora.desc()).all())
    ahora = datetime.now()
    proximas = [c for c in todas
                if c.fecha_hora >= ahora and c.estado in ("pendiente", "confirmada")]
    proximas.sort(key=lambda c: c.fecha_hora)
    historial = [c for c in todas if c not in proximas]
    return render_template("mis_citas.html", proximas=proximas, historial=historial)


@app.route("/citas/nueva", methods=["GET", "POST"])
@login_required
def cita_nueva():
    if current_user.es_doctor:
        flash("Las citas las agendan los clientes. Aquí está tu agenda.", "info")
        return redirect(url_for("agenda_doctor"))

    doctores = Usuario.query.filter_by(rol="doctor", activo=True).all()
    if not doctores:
        flash("Por ahora no hay doctores disponibles.", "error")
        return redirect(url_for("panel_cliente"))

    hoy = date.today()
    maximo = hoy + timedelta(days=DIAS_MAX_ANTICIPACION)

    # --- Confirmar la cita (cuando el cliente envía el formulario) ---
    if request.method == "POST":
        fecha_txt = request.form.get("fecha", "")
        hora_txt = request.form.get("hora", "")
        doctor_id = request.form.get("doctor_id", type=int)
        motivo = request.form.get("motivo", "").strip() or "Examen de la vista"

        doctor = next((d for d in doctores if d.id == doctor_id), None)
        try:
            fecha_hora = datetime.strptime(f"{fecha_txt} {hora_txt}", "%Y-%m-%d %H:%M")
        except ValueError:
            fecha_hora = None

        activas = Cita.query.filter(
            Cita.cliente_id == current_user.id,
            Cita.estado.in_(["pendiente", "confirmada"]),
            Cita.fecha_hora >= datetime.now()).count()

        if not doctor or not fecha_hora:
            flash("Elige un horario válido.", "error")
        elif fecha_hora not in horarios_del_dia(fecha_hora.date(), doctor.id):
            flash("Ese horario ya no está disponible. Elige otro.", "error")
        elif activas >= MAX_CITAS_ACTIVAS:
            flash(f"Ya tienes {MAX_CITAS_ACTIVAS} citas activas. "
                  "Cancela una o espera a que pase para agendar otra.", "error")
            return redirect(url_for("mis_citas"))
        else:
            try:
                db.session.add(Cita(cliente_id=current_user.id, doctor_id=doctor.id,
                                    fecha_hora=fecha_hora, motivo=motivo,
                                    estado="pendiente"))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Ese horario acaba de ser reservado por alguien más. Elige otro.", "error")
                return redirect(url_for("cita_nueva", fecha=fecha_txt, doctor=doctor_id))
            flash("¡Cita agendada! El doctor la confirmará pronto.", "exito")
            return redirect(url_for("mis_citas"))

        return redirect(url_for("cita_nueva", fecha=fecha_txt, doctor=doctor_id))

    # --- Mostrar los horarios libres del día elegido ---
    doctor_id = request.args.get("doctor", type=int)
    doctor = next((d for d in doctores if d.id == doctor_id), doctores[0])

    fecha = None
    horarios = None
    fecha_txt = request.args.get("fecha", "")
    if fecha_txt:
        try:
            fecha = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
        except ValueError:
            fecha = None
        if fecha and (fecha < hoy or fecha > maximo):
            flash(f"Elige una fecha entre hoy y los próximos {DIAS_MAX_ANTICIPACION} días.", "error")
            fecha = None
    if fecha:
        horarios = horarios_del_dia(fecha, doctor.id)

    return render_template("cita_nueva.html", doctores=doctores, doctor=doctor,
                           fecha=fecha, horarios=horarios, hoy=hoy, maximo=maximo)


@app.route("/citas/<int:cita_id>/cancelar", methods=["POST"])
@login_required
def cita_cancelar(cita_id):
    cita = db.get_or_404(Cita, cita_id)
    if cita.cliente_id != current_user.id:
        abort(403)
    if not puede_cancelar(cita):
        flash(f"Solo puedes cancelar con al menos {HORAS_MIN_CANCELAR} horas de anticipación. "
              "Comunícate con la óptica.", "error")
    else:
        cita.estado = "cancelada"
        db.session.commit()
        flash("Tu cita fue cancelada.", "info")
    return redirect(url_for("mis_citas"))


# ---------- Agenda del doctor ----------
@app.route("/doctor/agenda")
@solo_doctor
def agenda_doctor():
    try:
        fecha = datetime.strptime(request.args.get("fecha", ""), "%Y-%m-%d").date()
    except ValueError:
        fecha = date.today()

    inicio = datetime.combine(fecha, time(0, 0))
    citas = (Cita.query
             .filter(Cita.doctor_id == current_user.id,
                     Cita.fecha_hora >= inicio,
                     Cita.fecha_hora < inicio + timedelta(days=1))
             .order_by(Cita.fecha_hora).all())

    return render_template("agenda_doctor.html", citas=citas, fecha=fecha,
                           anterior=fecha - timedelta(days=1),
                           siguiente=fecha + timedelta(days=1),
                           hoy=date.today())


@app.route("/doctor/citas/<int:cita_id>/estado", methods=["POST"])
@solo_doctor
def doctor_cita_estado(cita_id):
    cita = db.get_or_404(Cita, cita_id)
    if cita.doctor_id != current_user.id:
        abort(403)

    nuevo = request.form.get("estado")
    if nuevo not in ("confirmada", "completada", "cancelada"):
        abort(400)

    cita.estado = nuevo
    db.session.commit()
    flash(f"Cita de {cita.cliente.nombre_completo}: {nuevo}.", "exito")
    return redirect(url_for("agenda_doctor", fecha=cita.fecha_hora.date().isoformat()))


# ---------- Test de visión ----------
NIVELES_AGUDEZA = ["20/200", "20/100", "20/60", "20/40", "20/30", "20/20"]
NOMBRES_TEST = {
    "agudeza": "Agudeza visual",
    "daltonismo": "Visión de colores",
    "astigmatismo": "Astigmatismo (líneas)",
}
TOTALES_TEST = {"agudeza": len(NIVELES_AGUDEZA), "daltonismo": 5, "astigmatismo": 1}


def solo_cliente(f):
    """Las pruebas son solo para clientes con sesión iniciada."""
    @wraps(f)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.es_doctor:
            flash("Las pruebas de visión son para los clientes.", "info")
            return redirect(url_for("panel_doctor"))
        return f(*args, **kwargs)
    return envoltura


def interpretar_resultado(tipo, puntaje, total, detalle):
    """Devuelve (mensaje, nivel). El nivel es 'bien' o 'atencion'."""
    ojo = detalle.get("ojo", "")
    ojo_txt = f" ({ojo})" if ojo else ""

    if tipo == "agudeza":
        if puntaje >= 5:
            return (f"Agudeza visual{ojo_txt}: lograste ver hasta la línea "
                    f"{NIVELES_AGUDEZA[puntaje - 1]}. Es un resultado dentro de lo esperado.",
                    "bien")
        mejor = NIVELES_AGUDEZA[puntaje - 1] if puntaje > 0 else "más grande que 20/200"
        return (f"Agudeza visual{ojo_txt}: tu mejor línea fue {mejor}. "
                "Te recomendamos agendar un examen visual completo.", "atencion")

    if tipo == "daltonismo":
        if not detalle.get("control_ok", True):
            return ("No identificaste la lámina de control, así que este resultado no es "
                    "confiable. Repite la prueba con buena luz, el brillo alto y sin "
                    "filtros de pantalla.", "atencion")
        if puntaje >= 4:
            return (f"Identificaste {puntaje} de {total} láminas. No se observan indicios "
                    "de dificultad para distinguir colores.", "bien")
        return (f"Identificaste {puntaje} de {total} láminas. Podría haber dificultad para "
                "distinguir algunos colores; el doctor puede confirmarlo con una prueba "
                "clínica.", "atencion")

    if tipo == "astigmatismo":
        if puntaje == 1:
            return (f"Viste todas las líneas con la misma nitidez{ojo_txt}.", "bien")
        return (f"Notaste líneas más oscuras o borrosas que otras{ojo_txt}. Puede ser señal "
                "de astigmatismo; te recomendamos un examen visual.", "atencion")

    return ("Resultado guardado.", "bien")


@app.route("/test")
@solo_cliente
def test_inicio():
    return render_template("test_inicio.html")


@app.route("/test/agudeza")
@solo_cliente
def test_agudeza():
    return render_template("test_agudeza.html")


@app.route("/test/daltonismo")
@solo_cliente
def test_daltonismo():
    return render_template("test_daltonismo.html")


@app.route("/test/astigmatismo")
@solo_cliente
def test_astigmatismo():
    return render_template("test_astigmatismo.html")


@app.route("/test/guardar", methods=["POST"])
@login_required
def test_guardar():
    if current_user.es_doctor:
        return jsonify(ok=False, mensaje="Solo los clientes pueden guardar pruebas."), 403

    datos = request.get_json(silent=True) or {}
    tipo = datos.get("tipo")
    puntaje = datos.get("puntaje")
    total = datos.get("total")
    detalle = datos.get("detalle") if isinstance(datos.get("detalle"), dict) else {}

    valido = (tipo in TOTALES_TEST
              and isinstance(puntaje, int) and isinstance(total, int)
              and total == TOTALES_TEST[tipo]
              and 0 <= puntaje <= total)
    if not valido:
        return jsonify(ok=False, mensaje="Los datos de la prueba no son válidos."), 400

    # Nos quedamos solo con los campos que esperamos
    limpio = {}
    for clave in ("ojo", "respuesta"):
        if clave in detalle:
            limpio[clave] = str(detalle[clave])[:30]
    if "control_ok" in detalle:
        limpio["control_ok"] = bool(detalle["control_ok"])

    db.session.add(ResultadoTest(cliente_id=current_user.id, tipo=tipo,
                                 puntaje=puntaje, total=total,
                                 detalle=json.dumps(limpio, ensure_ascii=False)))
    db.session.commit()

    mensaje, nivel = interpretar_resultado(tipo, puntaje, total, limpio)
    return jsonify(ok=True, mensaje=mensaje, nivel=nivel)


@app.route("/test/historial")
@solo_cliente
def test_historial():
    resultados = (ResultadoTest.query.filter_by(cliente_id=current_user.id)
                  .order_by(ResultadoTest.fecha.desc()).all())
    filas = []
    for r in resultados:
        try:
            detalle = json.loads(r.detalle or "{}")
        except ValueError:
            detalle = {}
        mensaje, nivel = interpretar_resultado(r.tipo, r.puntaje or 0, r.total or 1, detalle)
        filas.append({"fecha": r.fecha, "nombre": NOMBRES_TEST.get(r.tipo, r.tipo),
                      "mensaje": mensaje, "nivel": nivel})
    return render_template("test_historial.html", filas=filas)


# ---------- Panel del doctor: clientes, recetas y reprogramación ----------
CAMPOS_RECETA = [
    # (campo en la base de datos, nombre para mostrar, mínimo, máximo)
    ("od_esfera", "Esfera OD", -20, 20),
    ("od_cilindro", "Cilindro OD", -10, 10),
    ("od_eje", "Eje OD", 0, 180),
    ("oi_esfera", "Esfera OI", -20, 20),
    ("oi_cilindro", "Cilindro OI", -10, 10),
    ("oi_eje", "Eje OI", 0, 180),
    ("adicion", "Adición", 0, 4),
    ("distancia_pupilar", "Distancia pupilar", 40, 80),
]


@app.template_filter("dioptria")
def dioptria(valor):
    return "—" if valor is None else f"{valor:+.2f}"


@app.template_filter("grados")
def grados(valor):
    return "—" if valor is None else f"{valor}°"


@app.template_filter("edad")
def edad(fecha_nac):
    if not fecha_nac:
        return "—"
    hoy = date.today()
    return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))


def obtener_cliente_o_404(cliente_id):
    cliente = db.get_or_404(Usuario, cliente_id)
    if cliente.rol != "cliente":
        abort(404)
    return cliente


def leer_medida(campo, etiqueta, minimo, maximo):
    """Lee un número del formulario. Devuelve (valor, error). Vacío = None."""
    texto = request.form.get(campo, "").strip().replace(",", ".")
    if texto == "":
        return None, None
    try:
        valor = float(texto)
    except ValueError:
        return None, f"{etiqueta} debe ser un número."
    if not minimo <= valor <= maximo:
        return None, f"{etiqueta} debe estar entre {minimo} y {maximo}."
    return valor, None


def armar_filas_test(resultados):
    """Convierte los resultados de pruebas en filas con su interpretación."""
    filas = []
    for r in resultados:
        try:
            detalle = json.loads(r.detalle or "{}")
        except ValueError:
            detalle = {}
        mensaje, nivel = interpretar_resultado(r.tipo, r.puntaje or 0, r.total or 1, detalle)
        filas.append({"fecha": r.fecha, "nombre": NOMBRES_TEST.get(r.tipo, r.tipo),
                      "mensaje": mensaje, "nivel": nivel})
    return filas


# --- Lista y búsqueda de clientes ---
@app.route("/doctor/clientes")
@solo_doctor
def doctor_clientes():
    q = request.args.get("q", "").strip()
    pagina = request.args.get("pagina", 1, type=int)

    consulta = Usuario.query.filter_by(rol="cliente")
    for palabra in q.split():
        patron = f"%{palabra}%"
        consulta = consulta.filter(or_(Usuario.nombre.ilike(patron),
                                       Usuario.apellidos.ilike(patron),
                                       Usuario.email.ilike(patron),
                                       Usuario.telefono.ilike(patron)))
    paginacion = (consulta.order_by(Usuario.apellidos, Usuario.nombre)
                  .paginate(page=pagina, per_page=15, error_out=False))
    return render_template("doctor_clientes.html", paginacion=paginacion, q=q)


# --- Registrar un cliente desde la óptica ---
@app.route("/doctor/clientes/nuevo", methods=["GET", "POST"])
@solo_doctor
def doctor_cliente_nuevo():
    datos = {}
    if request.method == "POST":
        datos = request.form
        nombre = request.form.get("nombre", "").strip()
        apellidos = request.form.get("apellidos", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        fecha_txt = request.form.get("fecha_nacimiento", "").strip()
        password = request.form.get("password", "")

        if not nombre or not apellidos or not email:
            flash("Nombre, apellidos y correo son obligatorios.", "error")
        elif len(password) < 8:
            flash("La contraseña temporal debe tener al menos 8 caracteres.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("Ya existe un usuario con ese correo.", "error")
        else:
            try:
                fecha_nac = datetime.strptime(fecha_txt, "%Y-%m-%d").date() if fecha_txt else None
            except ValueError:
                fecha_nac = None
            nuevo = Usuario(nombre=nombre, apellidos=apellidos, email=email,
                            telefono=telefono, fecha_nacimiento=fecha_nac, rol="cliente")
            nuevo.set_password(password)
            db.session.add(nuevo)
            db.session.commit()
            flash("Cliente registrado. Entrégale su contraseña temporal.", "exito")
            return redirect(url_for("doctor_expediente", cliente_id=nuevo.id))

    return render_template("doctor_cliente_form.html", datos=datos)


# --- Expediente del cliente ---
@app.route("/doctor/clientes/<int:cliente_id>")
@solo_doctor
def doctor_expediente(cliente_id):
    cliente = obtener_cliente_o_404(cliente_id)
    citas = (Cita.query.filter_by(cliente_id=cliente.id)
             .order_by(Cita.fecha_hora.desc()).all())
    recetas = (Receta.query.filter_by(cliente_id=cliente.id)
               .order_by(Receta.fecha.desc()).all())
    resultados = (ResultadoTest.query.filter_by(cliente_id=cliente.id)
                  .order_by(ResultadoTest.fecha.desc()).all())
    return render_template("doctor_expediente.html", cliente=cliente, citas=citas,
                           recetas=recetas, pruebas=armar_filas_test(resultados))


@app.route("/doctor/citas/<int:cita_id>/notas", methods=["POST"])
@solo_doctor
def doctor_cita_notas(cita_id):
    cita = db.get_or_404(Cita, cita_id)
    if cita.doctor_id != current_user.id:
        abort(403)
    cita.notas_doctor = request.form.get("notas", "").strip()[:2000]
    db.session.commit()
    flash("Notas guardadas.", "exito")
    return redirect(url_for("doctor_expediente", cliente_id=cita.cliente_id))


# --- Recetas ---
@app.route("/doctor/clientes/<int:cliente_id>/recetas/nueva", methods=["GET", "POST"])
@solo_doctor
def doctor_receta_nueva(cliente_id):
    cliente = obtener_cliente_o_404(cliente_id)

    # Si viene de una cita, la enlazamos (solo si es de este cliente y de este doctor)
    cita = None
    cita_id = request.values.get("cita", type=int)
    if cita_id:
        cita = db.session.get(Cita, cita_id)
        if not cita or cita.cliente_id != cliente.id or cita.doctor_id != current_user.id:
            cita = None

    if request.method == "POST":
        medidas = {}
        errores = []
        for campo, etiqueta, minimo, maximo in CAMPOS_RECETA:
            valor, error = leer_medida(campo, etiqueta, minimo, maximo)
            medidas[campo] = valor
            if error:
                errores.append(error)

        for lado in ("od", "oi"):
            cilindro = medidas[f"{lado}_cilindro"]
            if cilindro not in (None, 0) and medidas[f"{lado}_eje"] is None:
                errores.append(f"Si hay cilindro en {lado.upper()}, indica también el eje.")
        if all(v is None for v in medidas.values()):
            errores.append("Captura al menos una medida.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("doctor_receta_form.html", cliente=cliente,
                                   cita=cita, valores=request.form)

        receta = Receta(cliente_id=cliente.id, doctor_id=current_user.id,
                        cita_id=cita.id if cita else None,
                        observaciones=request.form.get("observaciones", "").strip()[:2000])
        for campo, valor in medidas.items():
            if valor is not None and campo.endswith("_eje"):
                valor = int(round(valor))
            setattr(receta, campo, valor)
        db.session.add(receta)

        if cita and "completar" in request.form and cita.estado in ("pendiente", "confirmada"):
            cita.estado = "completada"

        db.session.commit()
        flash("Receta guardada.", "exito")
        return redirect(url_for("receta_ver", receta_id=receta.id))

    return render_template("doctor_receta_form.html", cliente=cliente, cita=cita, valores={})


@app.route("/receta/<int:receta_id>")
@login_required
def receta_ver(receta_id):
    receta = db.get_or_404(Receta, receta_id)
    if not current_user.es_doctor and receta.cliente_id != current_user.id:
        abort(403)
    return render_template("receta_ver.html", r=receta)


@app.route("/recetas")
@solo_cliente
def mis_recetas():
    recetas = (Receta.query.filter_by(cliente_id=current_user.id)
               .order_by(Receta.fecha.desc()).all())
    return render_template("mis_recetas.html", recetas=recetas)


# --- Reprogramar una cita ---
@app.route("/doctor/citas/<int:cita_id>/reprogramar", methods=["GET", "POST"])
@solo_doctor
def doctor_reprogramar(cita_id):
    cita = db.get_or_404(Cita, cita_id)
    if cita.doctor_id != current_user.id:
        abort(403)
    if cita.estado not in ("pendiente", "confirmada"):
        flash("Solo se pueden reprogramar citas pendientes o confirmadas.", "error")
        return redirect(url_for("agenda_doctor", fecha=cita.fecha_hora.date().isoformat()))

    hoy = date.today()
    maximo = hoy + timedelta(days=DIAS_MAX_ANTICIPACION)

    if request.method == "POST":
        fecha_txt = request.form.get("fecha", "")
        hora_txt = request.form.get("hora", "")
        try:
            nueva = datetime.strptime(f"{fecha_txt} {hora_txt}", "%Y-%m-%d %H:%M")
        except ValueError:
            nueva = None

        if not nueva or nueva not in horarios_del_dia(nueva.date(), cita.doctor_id):
            flash("Ese horario no está disponible. Elige otro.", "error")
            return redirect(url_for("doctor_reprogramar", cita_id=cita.id, fecha=fecha_txt))

        cita.fecha_hora = nueva
        cita.estado = "confirmada"
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ese horario acaba de ser ocupado. Elige otro.", "error")
            return redirect(url_for("doctor_reprogramar", cita_id=cita.id, fecha=fecha_txt))
        flash(f"Cita reprogramada para el {fecha_larga(nueva.date())} a las {hora_12(nueva)}.", "exito")
        return redirect(url_for("agenda_doctor", fecha=nueva.date().isoformat()))

    fecha = None
    horarios = None
    try:
        fecha = datetime.strptime(request.args.get("fecha", ""), "%Y-%m-%d").date()
    except ValueError:
        fecha = None
    if fecha and (fecha < hoy or fecha > maximo):
        flash("Elige una fecha entre hoy y los próximos 60 días.", "error")
        fecha = None
    if fecha:
        horarios = horarios_del_dia(fecha, cita.doctor_id)

    return render_template("doctor_reprogramar.html", cita=cita, fecha=fecha,
                           horarios=horarios, hoy=hoy, maximo=maximo)


# ---------- Mi cuenta ----------
@app.route("/cuenta")
@login_required
def cuenta():
    return render_template("cuenta.html")


@app.route("/cuenta/perfil", methods=["POST"])
@login_required
def cuenta_perfil():
    nombre = request.form.get("nombre", "").strip()
    apellidos = request.form.get("apellidos", "").strip()
    telefono = request.form.get("telefono", "").strip()
    fecha_txt = request.form.get("fecha_nacimiento", "").strip()

    if not nombre or not apellidos:
        flash("El nombre y los apellidos son obligatorios.", "error")
    else:
        try:
            fecha_nac = datetime.strptime(fecha_txt, "%Y-%m-%d").date() if fecha_txt else None
        except ValueError:
            fecha_nac = None

        current_user.nombre = nombre
        current_user.apellidos = apellidos
        current_user.telefono = telefono
        current_user.fecha_nacimiento = fecha_nac
        if current_user.es_doctor:
            current_user.cedula = request.form.get("cedula", "").strip()[:30]
        db.session.commit()
        flash("Tus datos fueron actualizados.", "exito")
    return redirect(url_for("cuenta"))


@app.route("/cuenta/password", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def cuenta_password():
    actual = request.form.get("actual", "")
    nueva = request.form.get("nueva", "")
    confirmar = request.form.get("confirmar", "")

    if not current_user.check_password(actual):
        flash("La contraseña actual no es correcta.", "error")
    elif len(nueva) < 8:
        flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
    elif nueva != confirmar:
        flash("Las contraseñas nuevas no coinciden.", "error")
    elif nueva == actual:
        flash("La nueva contraseña debe ser distinta de la actual.", "error")
    else:
        current_user.set_password(nueva)
        db.session.commit()
        flash("Contraseña actualizada.", "exito")
    return redirect(url_for("cuenta"))


@app.route("/privacidad")
def privacidad():
    return render_template("privacidad.html")


# ---------- Errores ----------
@app.errorhandler(403)
def acceso_denegado(e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("404.html"), 404


@app.errorhandler(413)
def archivo_muy_grande(e):
    flash("La imagen es demasiado grande (máximo 3 MB).", "error")
    return redirect(url_for("doctor_lentes"))


@app.errorhandler(CSRFError)
def error_csrf(e):
    if request.is_json:
        return jsonify(ok=False, mensaje="Tu sesión expiró. Recarga la página e inténtalo de nuevo."), 400
    flash("El formulario expiró o no es válido. Inténtalo de nuevo.", "error")
    return redirect(url_for("inicio"))


@app.errorhandler(429)
def demasiados_intentos(e):
    return render_template("error.html", titulo="Demasiados intentos",
                           mensaje="Espera unos minutos antes de intentarlo de nuevo."), 429


@app.errorhandler(500)
def error_interno(e):
    db.session.rollback()
    return render_template("error.html", titulo="Algo salió mal",
                           mensaje="Ocurrió un error inesperado. Inténtalo de nuevo en un momento."), 500


# ---------- Arranque (siempre va al FINAL del archivo) ----------
if __name__ == "__main__":
    with app.app_context():
        crear_datos_iniciales()
    app.run(debug=os.environ.get("PRODUCCION") != "1")
