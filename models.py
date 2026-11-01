from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    cedula = db.Column(db.String(30))  # cédula profesional (solo para el doctor)
    fecha_nacimiento = db.Column(db.Date)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default="cliente")  # "cliente" o "doctor"
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_doctor(self):
        return self.rol == "doctor"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"


class Lente(db.Model):
    __tablename__ = "lentes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(60), nullable=False)
    forma = db.Column(db.String(40))      # redondo, cuadrado, aviador...
    material = db.Column(db.String(40))   # acetato, metal, titanio...
    color = db.Column(db.String(40))
    genero = db.Column(db.String(20))     # hombre, mujer, unisex, niño
    precio = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.Text)
    imagen = db.Column(db.String(200))    # nombre del archivo en static/img
    disponible = db.Column(db.Boolean, default=True)


class Cita(db.Model):
    __tablename__ = "citas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False)
    motivo = db.Column(db.String(200))
    estado = db.Column(db.String(20), default="pendiente")
    # pendiente, confirmada, cancelada, completada
    notas_doctor = db.Column(db.Text)
    creada_en = db.Column(db.DateTime, default=datetime.now)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id],
                              backref="citas_como_cliente")
    doctor = db.relationship("Usuario", foreign_keys=[doctor_id],
                             backref="citas_como_doctor")


class ResultadoTest(db.Model):
    __tablename__ = "resultados_test"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tipo = db.Column(db.String(40), nullable=False)  # agudeza, daltonismo, astigmatismo
    puntaje = db.Column(db.Integer)
    total = db.Column(db.Integer)
    detalle = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.now)

    cliente = db.relationship("Usuario", backref="resultados_test")


class Receta(db.Model):
    __tablename__ = "recetas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    cita_id = db.Column(db.Integer, db.ForeignKey("citas.id"))

    # Ojo derecho (OD)
    od_esfera = db.Column(db.Float)
    od_cilindro = db.Column(db.Float)
    od_eje = db.Column(db.Integer)
    # Ojo izquierdo (OI)
    oi_esfera = db.Column(db.Float)
    oi_cilindro = db.Column(db.Float)
    oi_eje = db.Column(db.Integer)

    adicion = db.Column(db.Float)
    distancia_pupilar = db.Column(db.Float)
    observaciones = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.now)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id],
                              backref="recetas_como_cliente")
    doctor = db.relationship("Usuario", foreign_keys=[doctor_id],
                             backref="recetas_como_doctor")