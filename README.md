# 👓 Óptica HomSa

Aplicación web para una óptica que permite **agendar citas**, **consultar un catálogo de lentes** y **realizar un test de visión** en línea. Tiene acceso separado para los **clientes** y para el **doctor**, cada uno con su propio panel.

> 🔗 **Aplicación en línea:** opticahomsa.pythonanywhere.com

> ⚠️ Las pruebas de visión de la aplicación son una **orientación rápida**. No sustituyen un examen visual con el doctor ni sirven para diagnosticar.

---

## 📋 Características

### Clientes
- Registro (con aceptación del aviso de privacidad) e inicio de sesión.
- **Catálogo de lentes** con búsqueda, filtros (marca, forma, material, género y rango de precio), ordenamiento y página de detalle de cada modelo.
- **Citas:** elegir un día, ver solo los horarios libres, agendar, consultar próximas citas e historial y cancelar con anticipación.
- **Test de visión:**
  - *Agudeza visual:* letras "E" con calibración de pantalla usando una tarjeta.
  - *Visión de colores:* láminas con números escondidos (la primera es de control).
  - *Astigmatismo:* rueda de líneas.
  - Historial de resultados con su interpretación.
- Consulta e impresión de sus **recetas**.
- **Mi cuenta:** editar datos personales y cambiar la contraseña.

### Doctor
- **Panel** con resumen: citas de hoy, citas por confirmar, total de clientes y de lentes.
- **Agenda por día:** confirmar, marcar como completada, cancelar y **reprogramar** citas.
- **Clientes:** búsqueda con paginación, registro de clientes desde la óptica y **expediente** (datos, citas, recetas y pruebas de visión).
- **Notas internas** por cita (el cliente no las ve).
- **Recetas:** esfera, cilindro y eje de ambos ojos, adición y distancia pupilar, con vista imprimible que incluye la cédula profesional.
- **Administración del catálogo:** agregar, editar, ocultar y eliminar lentes, con foto.

### Reglas de la óptica (configurables en `app.py`)

| Regla | Valor |
|---|---|
| Horario de atención | 8:00 am a 5:00 pm, lunes a viernes |
| Duración de cada cita | 30 minutos |
| Anticipación máxima para agendar | 60 días |
| Citas activas por cliente | máximo 3 |
| Cancelación por el cliente | hasta 2 horas antes de la cita |
| Citas dobles | no se permite reservar una hora ocupada (validación en código y en la base de datos) |

---

## 🛠️ Tecnologías

- **Python 3** y **Flask**
- **Flask-SQLAlchemy** con **SQLite**
- **Flask-Login** (sesiones), **Flask-WTF** (protección CSRF) y **Flask-Limiter** (límite de intentos)
- **Jinja2**, HTML, CSS y JavaScript (sin librerías externas)
- Publicada en **PythonAnywhere**

---

## 🗂️ Estructura del proyecto

```
optima_homsa/
├── app.py                 # Aplicación: configuración, rutas y reglas de negocio
├── models.py              # Tablas de la base de datos
├── iniciar_base.py        # Crea la base de datos y el doctor inicial
├── reset_password.py      # Restablece la contraseña de un usuario (uso administrativo)
├── requirements.txt       # Dependencias
├── README.md
├── static/
│   ├── css/estilos.css
│   ├── js/                # Pruebas de visión (agudeza, daltonismo, astigmatismo)
│   └── img/lentes/        # Fotos subidas del catálogo
└── templates/             # Páginas HTML (Jinja2)
```

---

## 🗄️ Base de datos

| Tabla | Contenido |
|---|---|
| `usuarios` | Clientes y doctor (campo `rol`), con contraseña cifrada |
| `lentes` | Catálogo: marca, forma, material, color, género, precio, foto |
| `citas` | Cliente, doctor, fecha y hora, motivo, estado y notas del doctor |
| `resultados_test` | Resultados de las pruebas de visión de cada cliente |
| `recetas` | Medidas de cada ojo, adición, distancia pupilar y observaciones |

---

## 🚀 Ejecutar en tu computadora

1. Instala **Python 3** (marcando *Add Python to PATH*).
2. Descarga o clona este repositorio y abre la carpeta en una terminal.
3. Crea y activa el entorno virtual:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
   (En Mac/Linux: `source venv/bin/activate`)
4. Instala las dependencias:
   ```
   pip install -r requirements.txt
   ```
5. Inicia la aplicación:
   ```
   python app.py
   ```
6. Abre **http://127.0.0.1:5000** en el navegador.

En el primer arranque se crea la base de datos `instance/optima.db`, un doctor de prueba (su correo y contraseña de desarrollo están en la función `crear_datos_iniciales()` de `app.py`) y algunos lentes de ejemplo. Los clientes se registran desde la página.

### Variables de entorno (archivo `.env`, solo para producción)

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | Clave secreta de las sesiones (una cadena larga y aleatoria) |
| `PRODUCCION` | `1` en el servidor: activa cookies seguras, desactiva el modo de depuración y no crea lentes de ejemplo |
| `DOCTOR_PASSWORD` | Contraseña del doctor que se crea al iniciar la base (obligatoria en producción) |
| `DOCTOR_EMAIL` | Correo del doctor inicial (opcional) |

El archivo `.env` **no se sube a GitHub** (está en `.gitignore`).

---

## 🔄 Cómo se opera la aplicación

**Cliente**
1. Se registra y acepta el aviso de privacidad.
2. Explora el catálogo y, si quiere, hace las pruebas de visión.
3. En **Agendar cita** elige el día, ve las horas libres y confirma. La cita queda *Pendiente*.
4. Consulta el estado de sus citas en **Mis citas** y sus recetas en **Mis recetas**.

**Doctor**
1. Inicia sesión y revisa la **Agenda** del día.
2. *Confirma* las citas pendientes, o las *reprograma* o *cancela* si es necesario.
3. Abre el **expediente** del cliente, escribe notas y registra la **receta**.
4. Marca la cita como *Completada* (se hace automáticamente al guardar la receta desde esa cita).
5. Mantiene actualizado el **catálogo** de lentes.

---

## 🔒 Seguridad

- Contraseñas almacenadas con hash (nunca en texto plano).
- Protección **CSRF** en todos los formularios y en las pruebas de visión.
- Límite de intentos en inicio de sesión, registro y cambio de contraseña.
- Sesión que expira a las 2 horas, cookies `HttpOnly` y `SameSite`, y `Secure` en producción.
- Cabeceras de seguridad y páginas con datos de salud sin caché.
- Control de acceso por rol: un cliente no puede abrir páginas del doctor ni datos de otros clientes.
- Validación de datos en el servidor (rangos de la receta, tipos de imagen, tamaño máximo de 3 MB).

---

## 🌐 Publicación

La aplicación está publicada en **PythonAnywhere** (cuenta gratuita). El proceso resumido: subir el código, crear el entorno virtual, configurar el archivo `.env`, ejecutar `python iniciar_base.py`, configurar el archivo WSGI en la pestaña *Web* y recargar la aplicación.

---

## 🧭 Limitaciones y mejoras futuras

- Recuperación de contraseña y recordatorios de cita por correo electrónico.
- Migraciones de base de datos con Flask-Migrate y paso a PostgreSQL o MySQL.
- Pruebas automatizadas.
- Láminas clínicas con licencia para la prueba de daltonismo.
- Respaldos automáticos de la base de datos.

---

## 👤 Autoría

- **Nombre:** Garcia Avila Maris Danae, Victor Uriel
- **Materia:** Programacion web
- **Grupo / Docente:** 8Y / Pizarro Gurrola Ruben
- **Fecha:** noviembre 3 2026
