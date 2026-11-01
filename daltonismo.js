(function () {
    const raiz = document.getElementById("test");
    const urlGuardar = raiz.dataset.guardar;

    const TAM = 340;
    const canvas = document.getElementById("lamina");
    const ctx = canvas.getContext("2d");
    const entrada = document.getElementById("respuesta");
    const infoLamina = document.getElementById("info-lamina");
    const pasoInicio = document.getElementById("paso-inicio");
    const pasoPrueba = document.getElementById("paso-prueba");
    const resultado = document.getElementById("resultado");
    const acciones = document.getElementById("acciones-final");

    // La primera lámina es de CONTROL: la ve cualquier persona (azul sobre amarillo)
    const PALETA_CONTROL = {
        figura: ["#1d3f8f", "#2a56b8", "#16306e", "#3a6bd1"],
        fondo: ["#f3d54a", "#f7e07a", "#e8c52e", "#fbea9b"],
    };
    // Las demás usan rojos/naranjas contra verdes, que es lo que confunde el daltonismo rojo-verde
    const PALETA_PRUEBA = {
        figura: ["#e8743b", "#f19a4a", "#d95d39", "#f2b36b", "#c9552f"],
        fondo: ["#8fb85a", "#a5c96b", "#7aa64e", "#b9d77f", "#6f9a45"],
    };

    let laminas = [];
    let indice = 0;
    let correctas = 0;
    let controlOk = false;

    function barajar(lista) {
        for (let i = lista.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [lista[i], lista[j]] = [lista[j], lista[i]];
        }
        return lista;
    }

    function generarLamina(digito, paleta) {
        // 1) Máscara: dónde queda el número
        const mascara = document.createElement("canvas");
        mascara.width = TAM;
        mascara.height = TAM;
        const mctx = mascara.getContext("2d");
        mctx.fillStyle = "#000";
        mctx.font = "bold 260px Arial, Helvetica, sans-serif";
        mctx.textAlign = "center";
        mctx.textBaseline = "middle";
        mctx.fillText(String(digito), TAM / 2, TAM / 2 + 10);
        const pixeles = mctx.getImageData(0, 0, TAM, TAM).data;

        function dentroDelNumero(x, y) {
            const posicion = (Math.round(y) * TAM + Math.round(x)) * 4 + 3;
            return pixeles[posicion] > 128;
        }

        // 2) Círculos de distintos tamaños que no se encimen
        const circulos = [];
        const centro = TAM / 2;
        const radioPlaca = TAM / 2 - 4;
        for (let intento = 0; intento < 14000; intento++) {
            const r = 3.5 + Math.random() * 7;
            const angulo = Math.random() * 2 * Math.PI;
            const distancia = Math.sqrt(Math.random()) * (radioPlaca - r);
            const x = centro + Math.cos(angulo) * distancia;
            const y = centro + Math.sin(angulo) * distancia;

            let libre = true;
            for (const c of circulos) {
                const dx = c.x - x, dy = c.y - y;
                const minimo = c.r + r + 1;
                if (dx * dx + dy * dy < minimo * minimo) { libre = false; break; }
            }
            if (libre) circulos.push({ x: x, y: y, r: r });
        }

        // 3) Pintar: colores de "figura" dentro del número, de "fondo" afuera
        ctx.clearRect(0, 0, TAM, TAM);
        for (const c of circulos) {
            const colores = dentroDelNumero(c.x, c.y) ? paleta.figura : paleta.fondo;
            ctx.fillStyle = colores[Math.floor(Math.random() * colores.length)];
            ctx.beginPath();
            ctx.arc(c.x, c.y, c.r, 0, 2 * Math.PI);
            ctx.fill();
        }
    }

    function mostrar() {
        const lamina = laminas[indice];
        generarLamina(lamina.digito, lamina.paleta);
        infoLamina.textContent = "Lámina " + (indice + 1) + " de " + laminas.length;
        entrada.value = "";
        entrada.focus();
    }

    function responder(texto) {
        const acierto = texto.trim() === String(laminas[indice].digito);
        if (indice === 0) {
            controlOk = acierto;      // la lámina de control no cuenta en el puntaje
        } else if (acierto) {
            correctas++;
        }
        indice++;
        if (indice >= laminas.length) {
            terminar();
        } else {
            mostrar();
        }
    }

    async function terminar() {
        pasoPrueba.hidden = true;
        const respuesta = await guardarResultado(urlGuardar, {
            tipo: "daltonismo",
            puntaje: correctas,
            total: laminas.length - 1,
            detalle: { control_ok: controlOk },
        });
        mostrarResultado(resultado, respuesta);
        acciones.hidden = false;
    }

    document.getElementById("btn-iniciar").addEventListener("click", function () {
        const digitos = barajar([2, 3, 4, 5, 6, 7, 8, 9]).slice(0, 6);
        laminas = digitos.map(function (d, i) {
            return { digito: d, paleta: i === 0 ? PALETA_CONTROL : PALETA_PRUEBA };
        });
        indice = 0; correctas = 0; controlOk = false;
        pasoInicio.hidden = true;
        pasoPrueba.hidden = false;
        mostrar();
    });

    document.getElementById("btn-responder").addEventListener("click", function () {
        responder(entrada.value);
    });
    document.getElementById("btn-no-veo").addEventListener("click", function () {
        responder("");
    });
    entrada.addEventListener("keydown", function (evento) {
        if (evento.key === "Enter") responder(entrada.value);
    });
})();