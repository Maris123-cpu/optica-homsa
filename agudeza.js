(function () {
    const raiz = document.getElementById("test");
    const urlGuardar = raiz.dataset.guardar;

    const MM_TARJETA = 85.6;           // ancho real de una tarjeta de banco
    const DIRECCIONES = ["arriba", "abajo", "izquierda", "derecha"];
    const GRADOS = { derecha: 0, abajo: 90, izquierda: 180, arriba: 270 };
    const INTENTOS_POR_LINEA = 3;      // letras que se muestran por línea
    const MIN_ACIERTOS = 2;            // aciertos para pasar a la siguiente línea

    // Tamaño real de la letra (en mm) para ver a 1 metro de distancia
    const NIVELES = [
        { etiqueta: "20/200", mm: 14.54 },
        { etiqueta: "20/100", mm: 7.27 },
        { etiqueta: "20/60", mm: 4.36 },
        { etiqueta: "20/40", mm: 2.91 },
        { etiqueta: "20/30", mm: 2.18 },
        { etiqueta: "20/20", mm: 1.45 },
    ];

    const pasoCalibrar = document.getElementById("paso-calibrar");
    const pasoConfig = document.getElementById("paso-config");
    const pasoPrueba = document.getElementById("paso-prueba");
    const tarjetaRef = document.getElementById("tarjeta-ref");
    const ajuste = document.getElementById("ajuste");
    const selectOjo = document.getElementById("ojo");
    const pantallaE = document.getElementById("pantalla-e");
    const infoLinea = document.getElementById("info-linea");
    const resultado = document.getElementById("resultado");
    const acciones = document.getElementById("acciones-final");
    const aviso = document.getElementById("aviso-pantalla");

    let pxPorMm = 1;
    let ojo = "ambos";
    let nivel = 0, intento = 0, aciertos = 0, superados = 0;
    let direccionActual = null;

    if (window.innerWidth < 600) {
        aviso.hidden = false;
    }

    // ---- Paso 1: calibrar con una tarjeta ----
    function actualizarTarjeta() {
        tarjetaRef.style.width = ajuste.value + "px";
    }
    ajuste.addEventListener("input", actualizarTarjeta);
    actualizarTarjeta();

    document.getElementById("btn-calibrado").addEventListener("click", function () {
        pxPorMm = Number(ajuste.value) / MM_TARJETA;
        pasoCalibrar.hidden = true;
        pasoConfig.hidden = false;
    });

    // ---- Paso 2: empezar ----
    document.getElementById("btn-iniciar").addEventListener("click", function () {
        ojo = selectOjo.value;
        nivel = 0; intento = 0; aciertos = 0; superados = 0;
        pasoConfig.hidden = true;
        pasoPrueba.hidden = false;
        mostrarLetra();
    });

    // ---- Dibujar la letra E con SVG ----
    function dibujarE(direccion, altoPx) {
        return '<svg width="' + altoPx + '" height="' + altoPx + '" viewBox="0 0 5 5" ' +
               'xmlns="http://www.w3.org/2000/svg">' +
               '<g transform="rotate(' + GRADOS[direccion] + ' 2.5 2.5)" fill="#000">' +
               '<rect x="0" y="0" width="1" height="5"/>' +
               '<rect x="0" y="0" width="5" height="1"/>' +
               '<rect x="0" y="2" width="5" height="1"/>' +
               '<rect x="0" y="4" width="5" height="1"/>' +
               '</g></svg>';
    }

    function mostrarLetra() {
        direccionActual = DIRECCIONES[Math.floor(Math.random() * DIRECCIONES.length)];
        pantallaE.innerHTML = dibujarE(direccionActual, NIVELES[nivel].mm * pxPorMm);
        infoLinea.textContent = "Línea " + (nivel + 1) + " de " + NIVELES.length;
    }

    // ---- Responder ----
    function responder(direccion) {
        if (pasoPrueba.hidden) return;

        if (direccion === direccionActual) aciertos++;
        intento++;

        if (intento < INTENTOS_POR_LINEA) {
            mostrarLetra();
            return;
        }

        // Terminó la línea: ¿pasó al siguiente nivel?
        if (aciertos >= MIN_ACIERTOS) {
            superados++;
            nivel++;
            intento = 0;
            aciertos = 0;
            if (nivel >= NIVELES.length) {
                terminar();
            } else {
                mostrarLetra();
            }
        } else {
            terminar();
        }
    }

    document.querySelectorAll("[data-dir]").forEach(function (boton) {
        boton.addEventListener("click", function () {
            responder(boton.dataset.dir);
        });
    });

    document.addEventListener("keydown", function (evento) {
        const teclas = {
            ArrowUp: "arriba", ArrowDown: "abajo",
            ArrowLeft: "izquierda", ArrowRight: "derecha",
        };
        if (teclas[evento.key] && !pasoPrueba.hidden) {
            evento.preventDefault();
            responder(teclas[evento.key]);
        }
    });

    // ---- Terminar y guardar ----
    async function terminar() {
        pasoPrueba.hidden = true;
        const respuesta = await guardarResultado(urlGuardar, {
            tipo: "agudeza",
            puntaje: superados,
            total: NIVELES.length,
            detalle: { ojo: ojo },
        });
        mostrarResultado(resultado, respuesta);
        acciones.hidden = false;
    }
})();