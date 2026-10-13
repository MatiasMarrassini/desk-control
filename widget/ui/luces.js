"use strict";
// Pestaña de un grupo de focos WiZ (maqueta: docs/superpowers/specs/maquetas/luces-cuarto.html).
const ICONOS_ESCENA = { 1: "🌊", 2: "💞", 3: "🌇", 4: "🎉", 5: "🔥", 6: "🛋️", 7: "🌲", 8: "🎨", 9: "⏰", 10: "🛏️",
  11: "🕯️", 12: "☀️", 13: "❄️", 14: "🌙", 15: "🎯", 16: "🍃", 17: "🌈", 18: "📺", 19: "🌱", 20: "🌸", 21: "🏖️",
  22: "🍂", 23: "🐠", 24: "🌴", 25: "🍹", 26: "🪩", 27: "🎄", 28: "🎃", 29: "🕯️", 30: "✨", 31: "💓", 32: "⚙️", 33: "🪔" };
// Color aproximado para DIBUJAR cada escena (en escenas el foco no informa su color real).
const COLOR_ESCENA = { 1: [0, 140, 255], 2: [255, 80, 140], 3: [255, 120, 40], 6: [255, 170, 90], 7: [60, 200, 90],
  8: [200, 170, 255], 9: [255, 190, 120], 10: [255, 150, 70], 11: [255, 190, 120], 12: [255, 244, 229], 13: [200, 225, 255],
  14: [255, 140, 60], 15: [245, 248, 255], 16: [255, 200, 140], 17: [255, 235, 220], 18: [180, 160, 255], 19: [220, 80, 255],
  20: [255, 170, 200], 21: [255, 200, 80], 22: [230, 120, 40], 23: [0, 90, 200], 24: [40, 180, 80], 25: [120, 230, 120],
  26: [200, 0, 255], 27: [255, 40, 40], 28: [255, 120, 0], 29: [255, 150, 50], 30: [255, 215, 140], 31: [255, 60, 120],
  32: [220, 140, 60], 33: [255, 170, 0] };
const MAX_FAVORITAS = 7;
const MODOS_LUZ = [["r", "g", "b"], ["temp"], ["sceneId"]];

// Igual que combinar() en widget/dispositivos/wiz.py: color, temperatura y escena se excluyen.
function combinarLuz(estado, params) {
  const nuevo = { ...estado };
  for (const modo of MODOS_LUZ) {
    if (modo.some((k) => k in params)) {
      for (const otro of MODOS_LUZ) if (otro !== modo) otro.forEach((k) => delete nuevo[k]);
    }
  }
  Object.assign(nuevo, params);
  delete nuevo.speed;
  return nuevo;
}

function tempRgb(k) {
  const t = Math.min(1, Math.max(0, (k - 2200) / 4300));
  const [a, m, b] = [[255, 160, 70], [255, 244, 229], [190, 220, 255]];
  const [x, y, u] = t < 0.5 ? [a, m, t * 2] : [m, b, (t - 0.5) * 2];
  return x.map((v, i) => Math.round(v + (y[i] - v) * u));
}

function colorDeLuz(estado, fase) {
  if (estado.sceneId === 4) return [[255, 0, 80], [0, 200, 255], [255, 200, 0], [140, 0, 255]][fase % 4];
  if (estado.sceneId === 5) return [255, 90 + ((fase * 37) % 50), 20];
  if (estado.sceneId) return COLOR_ESCENA[estado.sceneId] || [255, 200, 140];
  if (estado.r != null) return [estado.r, estado.g, estado.b];
  return tempRgb(estado.temp || 4200);
}

// Foco dibujado: el vidrio toma el color con la variable CSS --vidrio (ver luces.css).
function dibujarFoco() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 60 92");
  const forma = "M30 2 C14 2 3 14 3 29 C3 40 9 46 14 53 C17 57 18 61 18 65 H42 C42 61 43 57 46 53 C51 46 57 40 57 29 C57 14 46 2 30 2 Z";
  const agregar = (tag, atributos) => {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
    svg.append(el);
  };
  agregar("path", { d: forma, class: "ampolla" });
  agregar("ellipse", { cx: "21", cy: "20", rx: "9", ry: "12", fill: "#fff", opacity: ".22" });
  agregar("path", { d: forma, fill: "none", stroke: "rgba(255,255,255,.35)", "stroke-width": "1.2" });
  agregar("rect", { x: "18", y: "65", width: "24", height: "6", rx: "2", fill: "#c9c9cd" });
  agregar("rect", { x: "19", y: "71", width: "22", height: "5", rx: "2", fill: "#a9a9ae" });
  agregar("rect", { x: "20", y: "76", width: "20", height: "5", rx: "2", fill: "#c9c9cd" });
  agregar("path", { d: "M22 81 H38 L34 88 H26 Z", fill: "#2c2c30" });
  return svg;
}

class VistaLuces {
  constructor(d) {
    this.d = d;
    this.estado = { ...(d.estado || {}) };
    this.confirmado = { ...this.estado };
    this.focos = d.focos || [];
    this.sincronizados = d.sincronizados !== false;
    this.favoritas = d.favoritas || [];
    this.escenas = d.escenas || [];
    this.conexionActual = { estado: d.conexion || "espera" };
    this.modo = this.estado.r != null ? "color" : "blanco";
    this.arrastrando = null;
    this.focosAbiertos = false;
    this.fase = 0;
    this.animacion = null;
    this.ui = {};
    this.raiz = util.el("section", "panel-luces");
    this.construir();
    this.raiz.addEventListener("click", (e) => {
      if (!e.target.closest(".popover, .arcoiris, .boton-todas")) this.cerrarPopovers();
    });
    this.pintar();
    this.pintarConexion();
  }

  // ---- construcción ----
  construir() {
    this.ui.heroe = util.el("div", "heroe");
    this.ui.bulbos = this.focos.map(() => {
      const colgante = util.el("div", "colgante");
      const bulbo = util.el("div", "bulbo");
      bulbo.append(util.el("div", "halo"), dibujarFoco());
      colgante.append(util.el("div", "cable"), bulbo);
      this.ui.heroe.append(colgante);
      return bulbo;
    });

    const controles = util.el("div", "controles-luces");
    const fila = util.el("div", "fila-luces");
    this.ui.pwr = util.el("button", "pwr");
    this.ui.pwr.title = "Encender / apagar";
    this.ui.pwr.append(util.iconoEncendido());
    this.ui.pwr.addEventListener("click", () => this.enviar({ state: !this.estado.state }));
    this.ui.chip = util.el("div", "estado-chip");
    fila.append(this.ui.pwr, util.el("span", "crece"), this.ui.chip);
    this.ui.banner = util.el("div", "banner");

    controles.append(fila, this.ui.banner, this.tarjetaModo(), this.tarjetaBrillo(), this.tarjetaEscenas(), this.tarjetaFocos());

    this.ui.rueda = crearRueda({
      alCambiar: (c) => this.raiz.style.setProperty("--c", util.rgb(c)),
      alConfirmar: (c, cerrar) => { if (c) this.enviar({ r: c[0], g: c[1], b: c[2] }); if (cerrar) this.cerrarPopovers(); },
    });
    this.ui.lista = util.el("div", "popover lista-escenas");
    this.raiz.append(this.ui.heroe, controles, this.ui.rueda, this.ui.lista);
  }

  tarjetaModo() {
    const t = util.el("div", "tarjeta");
    const seg = util.el("div", "seg");
    this.ui.botonesModo = ["blanco", "color"].map((modo) => {
      const b = util.el("button", null, modo === "blanco" ? "Blanco" : "Color");
      b.addEventListener("click", () => { this.modo = modo; this.pintar(); });
      seg.append(b);
      return { b, modo };
    });
    this.ui.panelBlanco = util.el("div");
    const temp = util.el("input", "temp");
    temp.type = "range"; temp.min = "2200"; temp.max = "6500"; temp.step = "100";
    const etiquetas = util.el("div", "temp-etiquetas");
    this.ui.tempValor = util.el("b");
    etiquetas.append(util.el("span", null, "Cálido"), this.ui.tempValor, util.el("span", null, "Frío"));
    this.ui.temp = temp;
    this.conectarDeslizador(temp, "temp", (v) => `${v} K`, this.ui.tempValor);
    this.ui.panelBlanco.append(temp, etiquetas);

    this.ui.panelColor = util.el("div", "muestras");
    for (const c of COLORES_COMUNES) {
      const m = util.el("button", "muestra");
      m.style.background = `rgb(${util.rgb(c)})`;
      m.addEventListener("click", () => this.enviar({ r: c[0], g: c[1], b: c[2] }));
      this.ui.panelColor.append(m);
    }
    const arcoiris = util.el("button", "muestra arcoiris");
    arcoiris.title = "Cualquier color";
    arcoiris.addEventListener("click", () => this.alternarPopover(this.ui.rueda));
    this.ui.panelColor.append(arcoiris);
    t.append(seg, this.ui.panelBlanco, this.ui.panelColor);
    return t;
  }

  tarjetaBrillo() {
    const t = util.el("div", "tarjeta");
    const etiqueta = util.el("div", "etiqueta");
    this.ui.brilloValor = util.el("b", "valor");
    etiqueta.append(util.el("span", null, "Brillo"), this.ui.brilloValor);
    const input = util.el("input");
    input.type = "range"; input.min = "10"; input.max = "100";
    this.ui.brillo = input;
    this.conectarDeslizador(input, "dimming", (v) => `${v}%`, this.ui.brilloValor);
    t.append(etiqueta, input);
    return t;
  }

  // Envía como máximo cada 150 ms mientras se arrastra y el valor final al soltar.
  conectarDeslizador(input, clave, formato, etiqueta) {
    const limitado = util.limitar((v) => this.enviar({ [clave]: v }), 150);
    input.addEventListener("input", () => {
      this.arrastrando = clave;
      etiqueta.textContent = formato(input.value);
      limitado(Number(input.value));
    });
    input.addEventListener("change", () => {
      this.arrastrando = null;
      this.enviar({ [clave]: Number(input.value) });
    });
  }

  tarjetaEscenas() {
    const t = util.el("div", "tarjeta");
    const etiqueta = util.el("div", "etiqueta");
    const todas = util.el("button", "boton-todas", "Todas ▾");
    todas.addEventListener("click", () => { if (this.alternarPopover(this.ui.lista)) this.pintarListaEscenas(); });
    etiqueta.append(util.el("span", null, "Escenas"), todas);
    this.ui.grillaEscenas = util.el("div", "escenas");
    t.append(etiqueta, this.ui.grillaEscenas);
    return t;
  }

  tarjetaFocos() {
    this.ui.tarjetaFocos = util.el("div", "tarjeta");
    const titulo = util.el("button", "focos-titulo");
    titulo.append(util.el("span", null, `💡 Focos (${this.focos.length})`), util.el("span", null, "▾"));
    titulo.addEventListener("click", () => { this.focosAbiertos = !this.focosAbiertos; this.pintar(); });
    this.ui.listaFocos = util.el("div", "focos-lista");
    this.ui.tarjetaFocos.append(titulo, this.ui.listaFocos);
    return this.ui.tarjetaFocos;
  }

  // ---- acciones ----
  async enviar(params, mac = null) {
    const conEscena = "sceneId" in params ? { state: true, ...params } : params;
    if (mac) {
      const foco = this.focos.find((f) => f.mac === mac);
      if (foco) foco.estado = combinarLuz(foco.estado || {}, conEscena);
    } else {
      this.estado = combinarLuz(this.estado, conEscena);
    }
    this.pintar();
    let r;
    try { r = await pywebview.api.luces_enviar(this.d.id, conEscena, mac); } catch (e) { r = { ok: false, error: String(e) }; }
    if (!r.ok) {
      util.aviso(r.error || "No se pudo enviar", "error");
      this.estado = { ...this.confirmado };
      this.pintar();
    }
  }

  async sincronizar() {
    let r;
    try { r = await pywebview.api.luces_sincronizar(this.d.id); } catch (e) { r = { ok: false }; }
    if (!r.ok) util.aviso(r.error || "No se pudo sincronizar", "error");
  }

  async alternarFavorita(id) {
    const nuevas = this.favoritas.includes(id) ? this.favoritas.filter((x) => x !== id) : [...this.favoritas, id];
    if (nuevas.length > MAX_FAVORITAS) { util.aviso(`Hasta ${MAX_FAVORITAS} favoritas`, "error"); return; }
    const r = await pywebview.api.luces_favoritas(this.d.id, nuevas);
    if (!r.ok) { util.aviso(r.error, "error"); return; }
    this.favoritas = nuevas;
    this.pintarListaEscenas();
    this.pintar();
  }

  editarNombreFoco(foco, etiqueta) {
    const input = util.el("input");
    input.value = foco.nombre;
    input.maxLength = 40;
    etiqueta.replaceWith(input);
    input.focus();
    input.select();
    let terminado = false;
    const terminar = async (guardar) => {
      if (terminado) return;
      terminado = true;
      if (guardar && input.value.trim() && input.value.trim() !== foco.nombre) {
        const r = await pywebview.api.renombrar_foco(this.d.id, foco.mac, input.value);
        if (r.ok) foco.nombre = input.value.trim().replace(/\s+/g, " ");
        else util.aviso(r.error, "error");
      }
      this.pintar();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") terminar(true);
      if (e.key === "Escape") { e.stopPropagation(); terminar(false); }
    });
    input.addEventListener("blur", () => terminar(true));
  }

  alternarPopover(popover) {
    const abrir = !popover.classList.contains("abierto");
    this.cerrarPopovers();
    if (abrir) popover.classList.add("abierto");
    return abrir;
  }

  cerrarPopovers() {
    this.raiz.querySelectorAll(".popover.abierto").forEach((p) => p.classList.remove("abierto"));
    this.pintar();
  }

  // ---- interfaz de vista (app.js) ----
  alMostrar() { pywebview.api.luces_visible(this.d.id, true); this.pintar(); }
  alOcultar() { pywebview.api.luces_visible(this.d.id, false); this.detenerAnimacion(); }

  estadoRecibido(datos) {
    this.confirmado = { ...datos.grupo };
    if (this.arrastrando) this.estado = { ...datos.grupo, [this.arrastrando]: this.estado[this.arrastrando] };
    else this.estado = { ...datos.grupo };
    this.focos = datos.focos.map((f) => ({ ...f, nombre: (this.focos.find((x) => x.mac === f.mac) || f).nombre }));
    this.sincronizados = datos.sincronizados;
    if (!this.arrastrando && datos.grupo.r != null) this.modo = "color";
    else if (!this.arrastrando && datos.grupo.temp != null) this.modo = "blanco";
    this.pintar();
  }

  conexion(info) {
    this.conexionActual = info;
    if (info.estado === "sin_respuesta") this.estado = { ...this.confirmado };
    this.pintarConexion();
    this.pintar();
  }

  errorRecibido({ mensaje }) { util.aviso(mensaje || "Error de los focos", "error"); }
  fuentesRecibidas() {}

  indicador() {
    const { estado, responden, total } = this.conexionActual;
    if (estado === "conectado") return { texto: "Conectadas", clase: "bien" };
    if (estado === "parcial") return { texto: `${responden} de ${total} conectadas`, clase: "bajo" };
    if (estado === "sin_respuesta") return { texto: "Sin respuesta", clase: "mal" };
    if (estado === "buscando") return { texto: "Buscando…", clase: "conectando" };
    return { texto: "En espera", clase: "espera" };
  }

  // ---- pintado ----
  detenerAnimacion() { if (this.animacion) { clearInterval(this.animacion); this.animacion = null; } }

  pintar() {
    const e = this.estado;
    const prendido = e.state !== false;
    const color = colorDeLuz(e, this.fase);
    const d = (e.dimming || 100) / 100;
    this.raiz.style.setProperty("--c", util.rgb(color));
    this.raiz.style.setProperty("--dg", prendido ? d : 0);
    this.raiz.classList.toggle("encendido", prendido);

    this.focos.forEach((foco, i) => {
      const propio = this.sincronizados ? e : { ...e, ...(foco.estado || {}) };
      const luce = foco.responde !== false && propio.state !== false;
      const bulbo = this.ui.bulbos[i];
      if (!bulbo) return;
      bulbo.classList.toggle("luce", luce);
      bulbo.style.setProperty("--l", util.rgb(colorDeLuz(propio, this.fase)));
      bulbo.style.setProperty("--dl", (propio.dimming || 100) / 100);
    });

    for (const { b, modo } of this.ui.botonesModo) b.classList.toggle("activo", modo === this.modo);
    this.ui.panelBlanco.style.display = this.modo === "blanco" ? "" : "none";
    this.ui.panelColor.style.display = this.modo === "color" ? "flex" : "none";
    if (this.arrastrando !== "temp") {
      this.ui.temp.value = e.temp || 4200;
      this.ui.tempValor.textContent = e.temp ? `${e.temp} K` : "–";
    }
    if (this.arrastrando !== "dimming") {
      this.ui.brillo.value = e.dimming || 100;
      this.ui.brilloValor.textContent = `${e.dimming || 100}%`;
    }
    this.pintarEscenas();
    this.pintarFocos();

    const animada = prendido && (e.sceneId === 4 || e.sceneId === 5) && this.raiz.isConnected;
    if (animada && !this.animacion) {
      this.animacion = setInterval(() => { this.fase++; this.pintar(); }, e.sceneId === 4 ? 700 : 300);
    }
    if (!animada) this.detenerAnimacion();
  }

  pintarEscenas() {
    const nombre = (id) => (this.escenas.find((s) => s.id === id) || { nombre: `Escena ${id}` }).nombre;
    const botones = this.favoritas.slice(0, MAX_FAVORITAS).map((id) => {
      const b = util.el("button", "escena" + (this.estado.sceneId === id ? " activa" : ""));
      b.append(util.el("span", null, ICONOS_ESCENA[id] || "✨"), util.el("span", null, nombre(id)));
      b.title = nombre(id);
      b.addEventListener("click", () => this.enviar({ sceneId: id }));
      return b;
    });
    const todas = util.el("button", "escena boton-todas");
    todas.append(util.el("span", null, "⋯"), util.el("span", null, "Todas"));
    todas.addEventListener("click", () => { if (this.alternarPopover(this.ui.lista)) this.pintarListaEscenas(); });
    this.ui.grillaEscenas.replaceChildren(...botones, todas);
  }

  pintarListaEscenas() {
    const seccion = (titulo, animada) => {
      const items = this.escenas.filter((s) => s.animada === animada).map((s) => {
        const fila = util.el("div", "item-escena");
        const elegir = util.el("button", "nombre", `${ICONOS_ESCENA[s.id] || "✨"}  ${s.nombre}`);
        elegir.addEventListener("click", () => { this.cerrarPopovers(); this.enviar({ sceneId: s.id }); });
        const estrella = util.el("button", "estrella" + (this.favoritas.includes(s.id) ? " marcada" : ""), "★");
        estrella.title = "Favorita";
        estrella.addEventListener("click", () => this.alternarFavorita(s.id));
        fila.append(elegir, estrella);
        return fila;
      });
      return [util.el("div", "etiqueta", titulo), ...items];
    };
    this.ui.lista.replaceChildren(...seccion("Fijas", false), ...seccion("Animadas", true));
  }

  pintarFocos() {
    this.ui.tarjetaFocos.classList.toggle("focos-abiertos", this.focosAbiertos);
    if (this.ui.listaFocos.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;
    const filas = this.focos.map((foco) => {
      const propio = this.sincronizados ? this.estado : { ...this.estado, ...(foco.estado || {}) };
      const luce = foco.responde !== false && propio.state !== false;
      const fila = util.el("div", "fila-foco" + (luce ? "" : " apagado"));
      fila.style.setProperty("--l", util.rgb(colorDeLuz(propio, this.fase)));
      const nombre = util.el("span", "nombre", foco.nombre);
      nombre.title = "Tocá para renombrar";
      nombre.addEventListener("click", () => this.editarNombreFoco(foco, nombre));
      fila.append(util.el("span", "mini"), nombre);
      if (foco.responde === false) fila.append(util.el("small", null, "sin respuesta"));
      const interruptor = util.el("button", "interruptor" + (luce ? " prendido" : ""));
      interruptor.title = luce ? "Apagar este foco" : "Encender este foco";
      interruptor.addEventListener("click", () => this.enviar({ state: !luce }, foco.mac));
      fila.append(interruptor);
      return fila;
    });
    const sincronizar = util.el("button", "sincronizar" + (this.sincronizados ? "" : " resaltado"), "⟳ Sincronizar los focos");
    sincronizar.addEventListener("click", () => this.sincronizar());
    this.ui.listaFocos.replaceChildren(...filas, sincronizar);
  }

  pintarConexion() {
    const { texto, clase } = this.indicador();
    this.ui.chip.className = `estado-chip ${clase}`;
    const total = this.focos.length;
    this.ui.chip.replaceChildren(util.el("span", "punto"),
      util.el("span", null, this.conexionActual.estado === "conectado" ? `${texto} · ${total} focos` : texto));
    const b = this.ui.banner;
    b.className = "banner";
    b.replaceChildren();
    if (this.conexionActual.estado === "sin_respuesta") {
      b.classList.add("visible", "mal");
      const info = util.el("div");
      info.append(util.el("div", null, "Los focos no responden."),
        util.el("small", null, "¿Tienen corriente? ¿La PC está en la misma red wifi? ¿Está activada la comunicación local en la app WiZ?"));
      const reintentar = util.el("button", "btn", "Reintentar");
      reintentar.addEventListener("click", () => pywebview.api.luces_reintentar(this.d.id));
      b.append(info, reintentar);
    }
    if (typeof pintarPestanas === "function") pintarPestanas();
  }
}
