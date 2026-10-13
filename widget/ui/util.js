"use strict";
// Ayudas comunes. Regla de seguridad: el texto se pone siempre con textContent (nunca innerHTML).
const util = {
  el(tag, clase, texto) {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    return e;
  },
  // Ejecuta fn como máximo cada `ms`; la última llamada siempre se ejecuta.
  limitar(fn, ms) {
    let ultimo = 0, pendiente = null;
    return (...args) => {
      const ahora = Date.now();
      clearTimeout(pendiente);
      if (ahora - ultimo >= ms) { ultimo = ahora; fn(...args); return; }
      pendiente = setTimeout(() => { ultimo = Date.now(); fn(...args); }, ms - (ahora - ultimo));
    };
  },
  // Ejecuta fn recién cuando pasan `ms` sin llamadas nuevas. `.cancelar()` descarta la pendiente.
  esperarQuieto(fn, ms) {
    let pendiente = null;
    const llamar = (...args) => {
      clearTimeout(pendiente);
      pendiente = setTimeout(() => fn(...args), ms);
    };
    llamar.cancelar = () => clearTimeout(pendiente);
    return llamar;
  },
  rgb(c) { return `${c[0]},${c[1]},${c[2]}`; },
  aviso(texto, tipo = "info") {
    const a = document.getElementById("aviso");
    a.textContent = texto;
    a.className = `aviso visible ${tipo}`;
    clearTimeout(util._temporizador);
    util._temporizador = setTimeout(() => { a.className = "aviso"; }, 3500);
  },
};
