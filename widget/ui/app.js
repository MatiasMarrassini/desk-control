"use strict";
// Estado global de la ventana, pestañas, indicador y eventos que llegan desde Python.
const app = { dispositivos: [], activo: null, vistas: new Map(), modo: "dispositivo", listo: false };

function crearVista(d) { return new VistaSable(d); }

async function recargarDatos() {
  const datos = await pywebview.api.inicial();
  app.dispositivos = datos.dispositivos;
  app.vistas = new Map(app.dispositivos.map((d) => [d.id, crearVista(d)]));
  if (!app.dispositivos.some((d) => d.id === app.activo)) app.activo = app.dispositivos[0]?.id ?? null;
}

function pintarPestanas() {
  const nav = document.getElementById("pestanas");
  nav.replaceChildren(...app.dispositivos.map((d) => {
    const activa = app.modo === "dispositivo" && d.id === app.activo;
    const b = util.el("button", "pestana" + (activa ? " activa" : ""), `⚔ ${d.nombre}`);
    b.addEventListener("click", () => mostrarDispositivo(d.id));
    return b;
  }));
}

function pintarIndicador() {
  const ind = document.getElementById("indicador");
  const vista = app.modo === "dispositivo" && app.activo ? app.vistas.get(app.activo) : null;
  if (!vista) { ind.className = "indicador"; ind.replaceChildren(); return; }
  const { texto, clase } = vista.indicador();
  ind.className = `indicador ${clase}`;
  ind.replaceChildren(util.el("span", "punto"), util.el("span", null, texto));
}

function vistaVacia() {
  const c = util.el("div", "vacio");
  const b = util.el("button", "btn primario", "Buscar dispositivos");
  b.addEventListener("click", mostrarBusqueda);
  c.append(util.el("div", "vacio-icono", "⚔"), util.el("p", null, "Todavía no agregaste dispositivos."), b);
  return c;
}

function mostrarDispositivo(id) {
  app.modo = "dispositivo";
  app.activo = id;
  const vista = id ? app.vistas.get(id) : null;
  document.getElementById("vista").replaceChildren(vista ? vista.raiz : vistaVacia());
  pintarPestanas();
  pintarIndicador();
}

function mostrarBusqueda() {
  app.modo = "busqueda";
  const busqueda = new VistaBusqueda({
    obtenerDispositivos: () => app.dispositivos,
    alVolver: () => mostrarDispositivo(app.activo),
    alGuardado: async (id) => { await recargarDatos(); mostrarDispositivo(id); },
    alCambiar: recargarDatos,
  });
  document.getElementById("vista").replaceChildren(busqueda.raiz);
  pintarPestanas();
  pintarIndicador();
  busqueda.buscar();
}

window.deskControl = {
  recibir(evento) {
    const vista = app.vistas.get(evento.id);
    if (!vista) return;
    if (evento.tipo === "estado") vista.estadoRecibido(evento.datos);
    else if (evento.tipo === "conexion") vista.conexion(evento.datos);
    else if (evento.tipo === "error") vista.errorRecibido(evento.datos);
    else if (evento.tipo === "fuentes") vista.fuentesRecibidas(evento.datos);
    pintarIndicador();
  },
  abrirBusqueda() { if (app.listo) mostrarBusqueda(); },
};

window.addEventListener("pywebviewready", async () => {
  document.getElementById("btn-ocultar").addEventListener("click", () => pywebview.api.ocultar());
  document.getElementById("btn-agregar").addEventListener("click", mostrarBusqueda);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.querySelector(".popover.abierto, .editor")) pywebview.api.ocultar();
  });
  await recargarDatos();
  app.listo = true;
  mostrarDispositivo(app.activo);
});
