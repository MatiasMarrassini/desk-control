"use strict";
// Panel de un sable Xeno3: dibujo animado + controles. Cumple la interfaz de vista de app.js.
const COLORES_COMUNES = [
  [255, 0, 0], [0, 80, 255], [0, 255, 0], [160, 0, 255],
  [255, 230, 0], [255, 120, 0], [0, 220, 255], [255, 255, 255],
];
const INTENTOS_CONEXION = 3;
const BATERIA_BAJA = 20;

class VistaSable {
  constructor(dispositivo) {
    this.d = dispositivo;
    this.d.estado = this.d.estado || {};
    this.d.fuentes = this.d.fuentes || [];
    this.confirmado = { ...this.d.estado };  // último estado que confirmó el sable
    this.conexionActual = { estado: dispositivo.conexion || "espera" };
    this.arrastrando = null;
    this.ui = {};
    this.raiz = util.el("section", "panel-sable");
    this.construir();
    this.raiz.addEventListener("click", (e) => {
      if (!e.target.closest(".popover, .arcoiris, .nombre-fuente")) this.cerrarPopovers();
    });
    this.pintar();
    this.pintarConexion();
  }

  // ---- construcción ----
  construir() {
    this.ui.banner = util.el("div", "banner");
    const escenario = util.el("div", "escenario");

    const sable = util.el("div", "sable");
    const mango = util.el("div", "mango");
    mango.append(util.el("div", "emisor"), util.el("div", "grip"), util.el("div", "pomo"));
    sable.append(util.el("div", "hoja"), mango);

    const controles = util.el("div", "controles");
    const filaPwr = util.el("div", "fila-centro");
    this.ui.pwr = util.el("button", "pwr", "⏻");
    this.ui.pwr.title = "Encender / apagar la hoja";
    this.ui.pwr.addEventListener("click", () => this.enviar("PowerOn", !this.d.estado.PowerOn));
    filaPwr.append(this.ui.pwr);
    controles.append(filaPwr, this.tarjetaColor(), this.deslizador("Volume", "Volumen"),
      this.deslizador("Brightness", "Brillo"), this.tarjetaFuente());
    escenario.append(sable, controles);

    this.ui.rueda = crearRueda({
      alCambiar: (c) => this.raiz.style.setProperty("--c", util.rgb(c)),
      alConfirmar: (c, cerrar) => {
        if (c) this.enviar("BackgroundColor", c);
        if (cerrar) this.cerrarPopovers();
      },
    });
    this.ui.lista = util.el("div", "popover lista-fuentes");
    this.raiz.append(this.ui.banner, escenario, this.ui.rueda, this.ui.lista);
  }

  tarjetaColor() {
    const t = util.el("div", "tarjeta");
    const muestras = util.el("div", "muestras");
    this.ui.muestras = COLORES_COMUNES.map((c) => {
      const m = util.el("button", "muestra");
      m.style.background = `rgb(${util.rgb(c)})`;
      m.title = `RGB ${c.join(", ")}`;
      m.addEventListener("click", () => this.enviar("BackgroundColor", c));
      muestras.append(m);
      return { el: m, color: c };
    });
    const arcoiris = util.el("button", "muestra arcoiris");
    arcoiris.title = "Cualquier color";
    arcoiris.addEventListener("click", () => this.alternarPopover(this.ui.rueda));
    muestras.append(arcoiris);
    t.append(util.el("div", "etiqueta", "Color"), muestras);
    return t;
  }

  deslizador(clave, titulo) {
    const t = util.el("div", "tarjeta");
    const etiqueta = util.el("div", "etiqueta");
    const valor = util.el("b", "valor");
    etiqueta.append(util.el("span", null, titulo), valor);
    const input = util.el("input");
    input.type = "range";
    input.min = "0";
    input.max = "100";
    const enviarLimitado = util.limitar((v) => this.enviar(clave, v), 150);
    input.addEventListener("input", () => {
      this.arrastrando = clave;
      valor.textContent = `${input.value}%`;
      enviarLimitado(Number(input.value));
    });
    input.addEventListener("change", () => {
      this.arrastrando = null;
      this.enviar(clave, Number(input.value));
    });
    t.append(etiqueta, input);
    this.ui[clave] = { input, valor };
    return t;
  }

  tarjetaFuente() {
    const t = util.el("div", "tarjeta fuente");
    this.ui.tarjetaFuente = t;
    const anterior = util.el("button", "flecha", "‹");
    const siguiente = util.el("button", "flecha", "›");
    const nombre = util.el("button", "nombre-fuente");
    nombre.title = "Ver todas las fuentes";
    this.ui.fuenteNombre = util.el("b");
    this.ui.fuenteNumero = util.el("small");
    nombre.append(this.ui.fuenteNombre, util.el("span", "flechita", " ▾"), util.el("br"), this.ui.fuenteNumero);
    anterior.addEventListener("click", () => this.moverFuente(-1));
    siguiente.addEventListener("click", () => this.moverFuente(1));
    nombre.addEventListener("click", () => this.abrirListaFuentes());
    t.append(anterior, nombre, siguiente);
    return t;
  }

  // ---- acciones ----
  async enviar(clave, valor) {
    this.d.estado[clave] = valor;  // vista optimista: se ve el cambio al instante
    this.pintar();
    let r;
    try { r = await pywebview.api.sable_enviar(this.d.id, clave, valor); } catch (e) { r = { ok: false, error: String(e) }; }
    if (!r.ok) {
      util.aviso(r.error || "No se pudo enviar", "error");
      this.revertir(clave);
    }
  }

  revertir(clave) {
    if (clave in this.confirmado) this.d.estado[clave] = this.confirmado[clave];
    else delete this.d.estado[clave];
    this.pintar();
  }

  totalFuentes() { return this.d.estado.TotalSoundPackage || this.d.fuentes.length || 0; }

  moverFuente(paso) {
    const total = this.totalFuentes();
    if (!total) return;
    const actual = this.d.estado.CurrentSoundPackageNo ?? 0;
    this.elegirFuente((actual + paso + total) % total);
  }

  elegirFuente(indice) {
    this.cerrarPopovers();
    if (this.d.fuentes[indice]) this.d.estado.fontname = this.d.fuentes[indice];
    this.enviar("CurrentSoundPackageNo", indice);
  }

  async abrirListaFuentes() {
    const abierta = this.alternarPopover(this.ui.lista);
    if (abierta && !this.d.fuentes.length) await this.cargarFuentes(false);
  }

  async cargarFuentes(refrescar) {
    this.ui.lista.replaceChildren(util.el("div", "cargando", "Leyendo fuentes del sable…"));
    let r;
    try { r = await pywebview.api.sable_fuentes(this.d.id, refrescar); } catch (e) { r = { ok: false }; }
    if (r.ok) this.fuentesRecibidas(r.fuentes);
    else this.ui.lista.replaceChildren(util.el("div", "cargando", r.error || "No se pudo leer la lista"));
  }

  pintarListaFuentes() {
    const actual = this.d.estado.CurrentSoundPackageNo;
    const items = this.d.fuentes.map((nombre, i) => {
      const item = util.el("button", "item-fuente" + (i === actual ? " actual" : ""));
      item.append(util.el("small", null, String(i + 1)), util.el("span", null, nombre));
      item.addEventListener("click", () => this.elegirFuente(i));
      return item;
    });
    const refrescar = util.el("button", "item-fuente refrescar", "↻ Volver a leer la lista");
    refrescar.addEventListener("click", () => this.cargarFuentes(true));
    this.ui.lista.replaceChildren(util.el("div", "etiqueta", "Fuentes en el sable"), ...items, refrescar);
    if (actual != null && items[actual]) {  // centra la fuente actual sin mover el resto de la ventana
      this.ui.lista.scrollTop = items[actual].offsetTop - this.ui.lista.clientHeight / 2;
    }
  }

  // La lista se abre justo debajo de la tarjeta de fuente y ocupa el resto del alto disponible.
  ubicarLista() {
    const tarjeta = this.ui.tarjetaFuente.getBoundingClientRect();
    const panel = this.raiz.getBoundingClientRect();
    this.ui.lista.style.top = `${Math.round(tarjeta.bottom - panel.top + 6)}px`;
  }

  alternarPopover(popover) {
    const abrir = !popover.classList.contains("abierto");
    this.cerrarPopovers();
    if (abrir) {
      if (popover === this.ui.lista) this.ubicarLista();
      popover.classList.add("abierto");
      if (popover === this.ui.lista && this.d.fuentes.length) this.pintarListaFuentes();
    }
    return abrir;
  }

  cerrarPopovers() {
    this.raiz.querySelectorAll(".popover.abierto").forEach((p) => p.classList.remove("abierto"));
    this.pintar();  // si se previsualizó un color sin confirmar, vuelve al real
  }

  // ---- eventos desde Python ----
  estadoRecibido(cambios) {
    Object.assign(this.confirmado, cambios);
    for (const [clave, valor] of Object.entries(cambios)) {
      if (clave !== this.arrastrando) this.d.estado[clave] = valor;
    }
    this.pintar();
    if ("Power" in cambios || "PowerOn" in cambios) this.pintarConexion();
  }

  errorRecibido({ clave, mensaje }) {
    util.aviso(clave ? `El sable rechazó ${clave}: ${mensaje}` : mensaje, "error");
    this.revertir(clave);
  }

  conexion(info) {
    this.conexionActual = info;
    this.d.conexion = info.estado;
    // Si la conexión falló o se cortó, las órdenes pendientes se descartaron: mostrar lo que el sable confirmó.
    if (["espera", "no_encontrado", "sin_bluetooth"].includes(info.estado)) this.volverAConfirmado();
    this.pintarConexion();
  }

  volverAConfirmado() {
    for (const [clave, valor] of Object.entries(this.confirmado)) {
      if (clave !== this.arrastrando) this.d.estado[clave] = valor;
    }
    this.pintar();
  }

  fuentesRecibidas(lista) {
    this.d.fuentes = lista;
    if (this.ui.lista.classList.contains("abierto")) this.pintarListaFuentes();
    this.pintar();
  }

  indicador() {
    const estado = this.conexionActual.estado;
    const bateria = this.d.estado.Power;
    if (estado === "conectando") return { texto: "conectando", clase: "conectando" };
    if (estado === "no_encontrado") return { texto: "sin señal", clase: "mal" };
    if (estado === "sin_bluetooth") return { texto: "sin Bluetooth", clase: "mal" };
    const texto = bateria == null ? (estado === "conectado" ? "conectado" : "en espera") : `🔋 ${bateria}%`;
    if (estado !== "conectado") return { texto, clase: "espera" };
    return { texto, clase: this.bateriaBaja() ? "bajo" : "bien" };
  }

  // Con la hoja encendida el voltaje cae y la lectura baja: solo se considera fiable con la hoja apagada.
  bateriaBaja() {
    const e = this.d.estado;
    return e.Power != null && e.Power < BATERIA_BAJA && !e.PowerOn;
  }

  // ---- pintado ----
  pintar() {
    const e = this.d.estado;
    const color = Array.isArray(e.BackgroundColor) ? e.BackgroundColor : [0, 255, 0];
    this.raiz.style.setProperty("--c", util.rgb(color));
    this.raiz.classList.toggle("encendido", !!e.PowerOn);
    for (const m of this.ui.muestras) m.el.classList.toggle("elegida", m.color.join() === color.join());
    for (const clave of ["Volume", "Brightness"]) {
      const { input, valor } = this.ui[clave];
      if (clave === this.arrastrando) continue;
      if (e[clave] != null) input.value = e[clave];
      valor.textContent = e[clave] == null ? "–" : `${e[clave]}%`;
    }
    const n = e.CurrentSoundPackageNo;
    const total = this.totalFuentes();
    this.ui.fuenteNombre.textContent = (n != null && this.d.fuentes[n]) || e.fontname || "Fuente";
    this.ui.fuenteNumero.textContent = n == null ? "" : `Fuente ${n + 1}${total ? ` de ${total}` : ""}`;
  }

  pintarConexion() {
    const { estado, intento } = this.conexionActual;
    this.raiz.dataset.conexion = estado;
    const b = this.ui.banner;
    b.className = "banner";
    b.replaceChildren();
    if (estado === "conectando") {
      b.classList.add("visible");
      b.append(util.el("span", "spinner"), util.el("span", "crece", `Conectando… intento ${intento || 1} de ${INTENTOS_CONEXION}`));
    } else if (estado === "no_encontrado") {
      b.classList.add("visible", "mal");
      const texto = util.el("div");
      texto.append(util.el("div", null, "No encontré el sable."),
        util.el("small", null, "¿Está encendido y cerca? ¿Conectado al iPhone?"));
      const reintentar = util.el("button", "btn", "Reintentar");
      reintentar.addEventListener("click", () => pywebview.api.sable_reintentar(this.d.id));
      b.append(texto, reintentar);
    } else if (estado === "sin_bluetooth") {
      b.classList.add("visible", "mal");
      b.append(util.el("span", null, "Activá el Bluetooth de Windows y volvé a intentar."));
    } else if (estado === "conectado" && this.bateriaBaja()) {
      b.classList.add("visible", "bajo");
      b.append(util.el("span", null, "🔋 Batería baja: cargá el sable pronto"));
    }
    if (typeof pintarIndicador === "function") pintarIndicador();
  }
}
