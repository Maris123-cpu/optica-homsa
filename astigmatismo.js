(function () {
    const raiz = document.getElementById("test");
    const urlGuardar = raiz.dataset.guardar;

    const canvas = document.getElementById("rueda");
    const ctx = canvas.getContext("2d");
    const resultado = document.getElementById("resultado");
    const acciones = document.getElementById("acciones-final");
    const formulario = document.getElementById("paso-respuesta");

    // Dibuja 12 líneas que cruzan el centro (cada 15 grados)
    const centro = canvas.width / 2;
    const radio = centro - 12;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#000";
    ctx.lineWidth = 3;
    for (let i = 0; i < 12; i++) {
        const angulo = (Math.PI / 12) * i;
        const dx = Math.cos(angulo) * radio;
        const dy = Math.sin(angulo) * radio;
        ctx.beginPath();
        ctx.moveTo(centro - dx, centro - dy);
        ctx.lineTo(centro + dx, centro + dy);
        ctx.stroke();
    }
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(centro, centro, 14, 0, 2 * Math.PI);
    ctx.fill();

    document.getElementById("btn-guardar").addEventListener("click", async function () {
        const ojo = document.getElementById("ojo").value;
        const marcada = document.querySelector('input[name="respuesta"]:checked');
        if (!marcada) {
            alert("Elige una respuesta antes de guardar.");
            return;
        }
        const igual = marcada.value === "igual";

        formulario.hidden = true;
        const respuesta = await guardarResultado(urlGuardar, {
            tipo: "astigmatismo",
            puntaje: igual ? 1 : 0,
            total: 1,
            detalle: { ojo: ojo, respuesta: marcada.value },
        });
        mostrarResultado(resultado, respuesta);
        acciones.hidden = false;
    });
})();