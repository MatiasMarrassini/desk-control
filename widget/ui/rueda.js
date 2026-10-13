"use strict";
// Rueda de color: el ángulo es el tono (rojo a la derecha, sentido horario) y la distancia al centro la saturación.
function colorEnRueda(dx, dy, radio) {
  const d = Math.min(1, Math.hypot(dx, dy) / radio);
  const h = ((((Math.atan2(dy, dx) * 180) / Math.PI) + 360) % 360) / 60;
  const x = 1 - Math.abs((h % 2) - 1);
  const base = [[1, x, 0], [x, 1, 0], [0, 1, x], [0, x, 1], [x, 0, 1], [1, 0, x]][Math.floor(h) % 6];
  return base.map((v) => Math.round(255 * (v * d + (1 - d))));
}

// alCambiar(color) se llama mientras se arrastra (vista previa); alConfirmar(color, cerrar) al soltar o con "Listo".
function crearRueda({ alCambiar, alConfirmar }) {
  const caja = util.el("div", "popover rueda-pop");
  const rueda = util.el("div", "rueda");
  const perilla = util.el("div", "perilla");
  rueda.append(perilla);
  const previa = util.el("span", "previa");
  const texto = util.el("span", null, "Tocá o arrastrá");
  const listo = util.el("button", "btn", "Listo");
  const pie = util.el("div", "rueda-pie");
  pie.append(previa, texto, util.el("span", "crece"), listo);
  caja.append(util.el("div", "etiqueta", "Elegí cualquier color"), rueda, pie);

  let color = null;
  let arrastrando = false;
  const mover = (e) => {
    const r = rueda.getBoundingClientRect();
    const radio = r.width / 2;
    let dx = e.clientX - r.left - radio;
    let dy = e.clientY - r.top - radio;
    const distancia = Math.hypot(dx, dy);
    if (distancia > radio) { dx *= radio / distancia; dy *= radio / distancia; }
    perilla.style.left = `${50 + (dx / r.width) * 100}%`;
    perilla.style.top = `${50 + (dy / r.height) * 100}%`;
    color = colorEnRueda(dx, dy, radio);
    previa.style.background = `rgb(${util.rgb(color)})`;
    texto.textContent = `RGB ${color.join(", ")}`;
    alCambiar(color);
  };
  rueda.addEventListener("pointerdown", (e) => { arrastrando = true; rueda.setPointerCapture(e.pointerId); mover(e); });
  rueda.addEventListener("pointermove", (e) => { if (arrastrando) mover(e); });
  rueda.addEventListener("pointerup", () => { arrastrando = false; if (color) alConfirmar(color, false); });
  listo.addEventListener("click", () => alConfirmar(color, true));
  return caja;
}
