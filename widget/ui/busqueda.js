"use strict";
// Pantalla "Agregar dispositivo" (diseño: docs/superpowers/specs/maquetas/estados-y-busqueda.html).
function nivelSenal(rssi) { return rssi >= -70 ? 4 : rssi >= -80 ? 3 : rssi >= -90 ? 2 : 1; }

function barrasSenal(rssi) {
  const s = util.el("span", "senal");
  const nivel = nivelSenal(rssi);
  for (let i = 1; i <= 4; i++) s.append(util.el("i", i <= nivel ? "llena" : null));
  s.title = `${rssi} dBm`;
  return s;
}

class VistaBusqueda {
  constructor({ obtenerDispositivos, alVolver, alGuardado, alCambiar }) {
    Object.assign(this, { obtenerDispositivos, alVolver, alGuardado, alCambiar });
    this.buscando = false;
    this.raiz = util.el("section", "panel-busqueda");
    const cabecera = util.el("div", "cabecera");
    const volver = util.el("button", "btn", "← Volver");
    volver.addEventListener("click", () => this.alVolver());
    this.estado = util.el("span", "estado-busqueda");
    const otraVez = util.el("button", "btn", "Buscar de nuevo");
    otraVez.addEventListener("click", () => this.buscar());
    cabecera.append(volver, util.el("span", "crece"), this.estado, otraVez);
    this.guardados = util.el("div", "lista");
    this.encontrados = util.el("div", "lista");
    this.raiz.append(cabecera, util.el("h2", null, "Agregar dispositivo"),
      util.el("div", "seccion", "Guardados"), this.guardados,
      util.el("div", "seccion", "Encontrados cerca"), this.encontrados);
    this.pintarGuardados();
  }

  async buscar() {
    if (this.buscando) return;
    this.buscando = true;
    this.estado.replaceChildren(util.el("span", "spinner"), util.el("span", null, "buscando…"));
    this.encontrados.replaceChildren();
    let r;
    try { r = await pywebview.api.buscar(); } catch (e) { r = { ok: false, error: "fallo" }; }
    this.buscando = false;
    this.estado.replaceChildren();
    if (!r.ok) {
      this.mensaje(this.encontrados, r.error === "sin_bluetooth"
        ? "Activá el Bluetooth de Windows y buscá de nuevo." : "No se pudo buscar. Probá de nuevo.");
      return;
    }
    const nuevos = r.encontrados.filter((s) => !s.guardado);
    const nota = r.error_bluetooth ? " (Bluetooth apagado: solo se buscaron focos)" : "";
    if (!nuevos.length) {
      this.mensaje(this.encontrados, `No encontré dispositivos nuevos${nota}. ¿Están encendidos y en la misma red?`);
      return;
    }
    this.encontrados.replaceChildren(...nuevos.map((s) => s.tipo === "wiz_grupo" ? this.filaGrupo(s) : this.filaEncontrado(s)));
    if (nota) util.aviso("Bluetooth apagado: solo se buscaron focos", "info");
  }

  mensaje(lista, texto) { lista.replaceChildren(util.el("div", "mensaje", texto)); }

  fila(icono, titulo, detalle) {
    const f = util.el("div", "dispositivo");
    const info = util.el("div", "info");
    const small = util.el("small");
    if (detalle instanceof Node) small.append(detalle); else small.textContent = detalle;
    info.append(util.el("b", null, titulo), small);
    f.append(util.el("div", "icono-disp", icono), info);
    return f;
  }

  filaEncontrado(s) {
    const detalle = util.el("span");
    detalle.append(barrasSenal(s.rssi), document.createTextNode(` Xeno3 · Bluetooth · ${s.direccion}`));
    const f = this.fila("⚔", s.nombre, detalle);
    const agregar = util.el("button", "btn primario", "＋ Agregar");
    agregar.addEventListener("click", () => this.editar(f, "Mi sable", async (nombre) => {
      const r = await pywebview.api.guardar_dispositivo(s.direccion, nombre);
      if (!r.ok) { util.aviso(r.error, "error"); return false; }
      await this.alGuardado(r.dispositivo.id);
      return true;
    }));
    f.append(agregar);
    return f;
  }

  filaGrupo(g) {
    const ips = g.focos.map((f) => f.ip).join(", ");
    const f = this.fila("💡", `${g.focos.length} ${g.focos.length === 1 ? "foco" : "focos"} WiZ`, `WiFi · ${ips}`);
    const agregar = util.el("button", "btn primario", "＋ Agregar");
    agregar.addEventListener("click", () => this.editar(f, g.nombre, async (nombre) => {
      const r = await pywebview.api.guardar_grupo(g.clave, nombre, g.focos);
      if (!r.ok) { util.aviso(r.error, "error"); return false; }
      await this.alGuardado(r.dispositivo.id);
      return true;
    }));
    f.append(agregar);
    return f;
  }

  pintarGuardados() {
    const lista = this.obtenerDispositivos();
    if (!lista.length) { this.mensaje(this.guardados, "Ninguno todavía."); return; }
    this.guardados.replaceChildren(...lista.map((d) => {
      const detalle = d.tipo === "wiz_grupo" ? `${d.focos.length} focos WiZ` : `Xeno3 · ${d.direccion}`;
      const f = this.fila(d.tipo === "wiz_grupo" ? "💡" : "⚔", d.nombre, detalle);
      const renombrar = util.el("button", "btn-icono", "✎");
      renombrar.title = "Renombrar";
      renombrar.addEventListener("click", () => this.editar(f, d.nombre, async (nombre) => {
        const r = await pywebview.api.renombrar_dispositivo(d.id, nombre);
        if (!r.ok) { util.aviso(r.error, "error"); return false; }
        await this.alCambiar();
        this.pintarGuardados();
        return true;
      }));
      const quitar = util.el("button", "btn-icono", "✕");
      quitar.title = "Quitar";
      quitar.addEventListener("click", () => this.confirmarQuitar(f, d));
      f.append(renombrar, quitar);
      return f;
    }));
  }

  editar(fila, nombreInicial, alGuardar) {
    if (fila.classList.contains("editando")) return;
    const editor = util.el("div", "editor");
    const input = util.el("input");
    input.value = nombreInicial;
    input.maxLength = 40;
    input.placeholder = "Nombre";
    const cancelar = util.el("button", "btn", "Cancelar");
    const guardar = util.el("button", "btn primario", "Guardar");
    const botones = util.el("div", "botones");
    botones.append(cancelar, guardar);
    editor.append(input, botones);
    fila.after(editor);
    fila.classList.add("editando");
    input.focus();
    input.select();
    const cerrar = () => { editor.remove(); fila.classList.remove("editando"); };
    const confirmar = async () => { if (await alGuardar(input.value)) cerrar(); };
    cancelar.addEventListener("click", cerrar);
    guardar.addEventListener("click", confirmar);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") confirmar();
      if (e.key === "Escape") { e.stopPropagation(); cerrar(); }
    });
  }

  confirmarQuitar(fila, d) {
    if (fila.classList.contains("editando")) return;
    const caja = util.el("div", "editor");
    caja.append(util.el("span", null, `¿Quitar "${d.nombre}"?`));
    const no = util.el("button", "btn", "No");
    const si = util.el("button", "btn peligro", "Quitar");
    const botones = util.el("div", "botones");
    botones.append(no, si);
    caja.append(botones);
    fila.after(caja);
    fila.classList.add("editando");
    no.addEventListener("click", () => { caja.remove(); fila.classList.remove("editando"); });
    si.addEventListener("click", async () => {
      await pywebview.api.quitar_dispositivo(d.id);
      await this.alCambiar();
      this.pintarGuardados();
    });
  }
}
