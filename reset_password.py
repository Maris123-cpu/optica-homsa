from app import app
from models import db, Usuario

correo = input("Correo del usuario: ").strip().lower()
nueva = input("Nueva contraseña (mínimo 8 caracteres): ")

with app.app_context():
    usuario = Usuario.query.filter_by(email=correo).first()

    if not usuario:
        print("No existe ningún usuario con ese correo.")
    elif len(nueva) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
    else:
        usuario.set_password(nueva)
        db.session.commit()
        print(f"Listo: la contraseña de {usuario.nombre_completo} fue cambiada.")