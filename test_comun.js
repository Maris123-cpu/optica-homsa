async function guardarResultado(url, datos) {
    const meta = document.querySelector('meta[name="csrf-token"]');
    try {
        const respuesta = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": meta ? meta.content : "",
            },
            body: JSON.stringify(datos),
        });
        return await respuesta.json();
    } catch (error) {
        return { ok: false, mensaje: "No se pudo guardar el resultado. Revisa tu conexión e inténtalo de nuevo." };
    }
}

function mostrarResultado(caja, respuesta) {
    let clase = "error";
    if (respuesta.ok) {
        clase = respuesta.nivel === "bien" ? "exito" : "info";
    }
    caja.className = "alerta " + clase;
    caja.textContent = respuesta.mensaje;
    caja.hidden = false;
}