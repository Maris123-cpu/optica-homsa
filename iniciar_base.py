"""Crea las tablas y el doctor inicial.

Se ejecuta UNA vez en el servidor (y de nuevo después de cada actualización
que cambie la base de datos):

    python iniciar_base.py
"""
from app import app, crear_datos_iniciales

with app.app_context():
    crear_datos_iniciales()

print("Base de datos lista.")
