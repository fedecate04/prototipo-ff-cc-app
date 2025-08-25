# -*- coding: utf-8 -*-
import os
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from PIL import Image

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# =========================
# Configuración general
# =========================
st.set_page_config(
    page_title="Prototipo O&G - Notificaciones y Trazabilidad",
    page_icon="🛢️",
    layout="wide",
)

ASSETS_DIR = Path("assets")
DATA_DIR = Path("data")
ASSETS_DIR.mkdir(exist_ok=True, parents=True)
DATA_DIR.mkdir(exist_ok=True, parents=True)

# Archivos de datos
F_USUARIOS   = DATA_DIR / "usuarios.csv"
F_ACTIVOS    = DATA_DIR / "activos.csv"
F_NOTIF      = DATA_DIR / "notificaciones.csv"
F_RONDAS_PLT = DATA_DIR / "rondas_plantillas.csv"
F_RONDAS_RUN = DATA_DIR / "rondas_ejecuciones.csv"
F_INCIDENTES = DATA_DIR / "incidentes.csv"
F_PTWOT      = DATA_DIR / "ptw_ot.csv"

# =========================
# Utilidades y persistencia
# =========================
def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_read_csv(path: Path, dtypes=None, parse_dates=None) -> pd.DataFrame:
    """Lectura segura de CSV (no rompe la app si hay corrupción)."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=dtypes, parse_dates=parse_dates, keep_default_na=False)
    except Exception as e:
        st.warning(f"Archivo dañado o no legible: {path.name}. Se carga vacío. Detalle: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_csv(path: Path, dtypes=None, parse_dates=None) -> pd.DataFrame:
    return _safe_read_csv(path, dtypes=dtypes, parse_dates=parse_dates)

def save_csv(df: pd.DataFrame, path: Path):
    # Para evitar problemas de permisos, se guarda atómicamente cuando es posible.
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)

def next_sequential_id(df: pd.DataFrame, id_col: str = "id") -> int:
    if df is None or df.empty or id_col not in df.columns:
        return 1
    try:
        return int(pd.to_numeric(df[id_col], errors="coerce").max()) + 1
    except Exception:
        return 1

# =========================
# Seed de datos si no existen
# =========================
def seed_if_missing():
    if not F_USUARIOS.exists():
        usuarios = pd.DataFrame([
            {"user_id": "op1", "nombre": "Operario 1", "rol": "Operario",   "area": "Operación Área B"},
            {"user_id": "op2", "nombre": "Operario 2", "rol": "Operario",   "area": "Operación Área A"},
            {"user_id": "sup1","nombre": "Supervisor 1","rol": "Supervisor","area": "Sala Control"},
            {"user_id": "hse1","nombre": "HSE 1",      "rol": "HSE",        "area": "HSE"},
        ])
        save_csv(usuarios, F_USUARIOS)

    if not F_ACTIVOS.exists():
        activos = pd.DataFrame([
            {"tag": "V-210",   "descripcion": "Válvula de control línea de producción", "area": "Área B"},
            {"tag": "P-101",   "descripcion": "Bomba de transferencia",                 "area": "Área A"},
            {"tag": "TK-1203", "descripcion": "Tanque crudo estabilizado",             "area": "Tanques"},
            {"tag": "K-301",   "descripcion": "Compresor gas baja presión",            "area": "Compresión"},
        ])
        save_csv(activos, F_ACTIVOS)

    if not F_NOTIF.exists():
        notif = pd.DataFrame([
            {"id": 1, "ts_creacion": now_iso(), "tag": "V-210", "titulo": "Chequear válvula V-210",
             "motivo": "Sobrepresión", "prioridad": "P1", "estado": "Pendiente",
             "asignado_a": "Operario 1", "ts_recibida": "", "ts_cerrada": "", "evidencia": ""},
            {"id": 2, "ts_creacion": now_iso(), "tag": "P-101", "titulo": "Verificar sello mecánico",
             "motivo": "Goteo observado", "prioridad": "P2", "estado": "Pendiente",
             "asignado_a": "Operario 2", "ts_recibida": "", "ts_cerrada": "", "evidencia": ""},
        ])
        save_csv(notif, F_NOTIF)

    if not F_RONDAS_PLT.exists():
        rondas = pd.DataFrame([
            {"plantilla": "Ronda Compresores", "tag": "K-301",   "variable": "Presión succión [bar]",      "lim_inf": 2.0,  "lim_sup": 5.0},
            {"plantilla": "Ronda Compresores", "tag": "K-301",   "variable": "Temperatura carcasa [°C]",   "lim_inf": 20.0, "lim_sup": 80.0},
            {"plantilla": "Ronda Tanques",     "tag": "TK-1203", "variable": "Nivel [%]",                   "lim_inf": 10.0, "lim_sup": 85.0},
            {"plantilla": "Ronda Tanques",     "tag": "TK-1203", "variable": "Temperatura [°C]",            "lim_inf": 10.0, "lim_sup": 60.0},
        ])
        save_csv(rondas, F_RONDAS_PLT)

    if not F_RONDAS_RUN.exists():
        save_csv(pd.DataFrame(columns=["id","ts","plantilla","tag","variable","valor","en_rango","operario"]), F_RONDAS_RUN)

    if not F_INCIDENTES.exists():
        inc = pd.DataFrame([
            {"id": 1, "ts": now_iso(), "tag": "V-210", "titulo": "Near Miss por sobrepresión",
             "severidad": "Medio", "descripcion": "Se detecta lectura por encima del umbral",
             "reportado_por": "Operario 1", "estado": "Abierto"},
        ])
        save_csv(inc, F_INCIDENTES)

    if not F_PTWOT.exists():
        ptw = pd.DataFrame([
            {"id": 1, "ts_solicitud": now_iso(), "tipo": "Trabajo caliente", "solicitante": "Supervisor 1",
             "area": "Área B", "estado": "Borrador", "aprob_hse": "No", "ts_cierre": "", "adjuntos": ""},
        ])
        save_csv(ptw, F_PTWOT)

seed_if_missing()

# =========================
# Carga de datos (cache)
# =========================
usuarios   = load_csv(F_USUARIOS)
activos    = load_csv(F_ACTIVOS)
notifs     = load_csv(F_NOTIF)
rondas_plt = load_csv(F_RONDAS_PLT)
rondas_run = load_csv(F_RONDAS_RUN)
incidentes = load_csv(F_INCIDENTES)
ptwot      = load_csv(F_PTWOT)

# =========================
# Helpers visuales
# =========================
def chip_estado(estado: str) -> str:
    palette = {
        "Pendiente": "🟡",
        "Recibida": "🟠",
        "Completada": "🟢",
        "Abierto": "🟠",
        "Cerrado": "🟢",
        "Borrador": "⚪",
        "Aprobado": "🟦",
    }
    return f"{palette.get(estado,'⚪')} {estado}"

def chip_prioridad(p: str) -> str:
    pal = {"P1":"🔴 P1","P2":"🟠 P2","P3":"🟡 P3","P4":"🟢 P4"}
    return pal.get(p, p)

# =========================
# UI – Header
# =========================
col_logo, col_title = st.columns([1, 5], vertical_alignment="center")
with col_logo:
    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        try:
            st.image(Image.open(logo_path), use_column_width=True)
        except Exception:
            st.write("🛢️")
    else:
        st.write("🛢️")
with col_title:
    st.markdown("### **Prototipo – Operaciones & HSE**")
    st.caption("Notificaciones • Rondas • PTW/OT • Incidentes • Dashboard")

# Sidebar navegación
page = st.sidebar.radio(
    "Navegación",
    ["Inicio", "Notificaciones", "Rondas", "PTW / OT", "Incidentes", "Dashboard", "Documentos", "Config & IoT"],
    index=0
)

# =========================
# Páginas
# =========================

# --------- INICIO ---------
if page == "Inicio":
    c1, c2, c3, c4 = st.columns(4)
    # KPIs
    k_total = len(notifs) if not notifs.empty else 0
    k_pend = int((notifs["estado"]=="Pendiente").sum()) if not notifs.empty else 0
    k_rec  = int((notifs["estado"]=="Recibida").sum())  if not notifs.empty else 0
    k_comp = int((notifs["estado"]=="Completada").sum()) if not notifs.empty else 0

    c1.metric("Notificaciones totales", k_total)
    c2.metric("Pendientes", k_pend)
    c3.metric("Recibidas", k_rec)
    c4.metric("Completadas", k_comp)

    st.divider()
    st.markdown("#### Actividad reciente")
    if not notifs.empty:
        st.dataframe(
            notifs.sort_values("ts_creacion", ascending=False).head(10),
            use_container_width=True
        )
    else:
        st.info("Sin notificaciones por ahora.")

# --------- NOTIFICACIONES ---------
elif page == "Notificaciones":
    st.markdown("### 📨 Notificaciones operativas")
    with st.expander("➕ Crear nueva notificación", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tag = st.selectbox("Equipo/Tag", activos["tag"].unique())
            titulo = st.text_input("Título", value=f"Chequear {tag}")
        with col2:
            motivo = st.text_input("Motivo", value="Lectura fuera de rango")
            prioridad = st.selectbox("Prioridad", ["P1","P2","P3","P4"], index=1)
        with col3:
            asignado = st.selectbox("Asignar a", usuarios["nombre"].tolist())

        if st.button("Crear notificación", use_container_width=True, type="primary"):
            # reset cache de notifs tras escritura
            new_id = next_sequential_id(notifs, "id")
            new_row = {
                "id": new_id, "ts_creacion": now_iso(), "tag": tag,
                "titulo": titulo, "motivo": motivo, "prioridad": prioridad,
                "estado": "Pendiente", "asignado_a": asignado,
                "ts_recibida": "", "ts_cerrada": "", "evidencia": ""
            }
            notifs = pd.concat([notifs, pd.DataFrame([new_row])], ignore_index=True)
            save_csv(notifs, F_NOTIF)
            st.cache_data.clear()  # asegura recarga en esta sesión
            st.success(f"Notificación creada (ID {new_id}).")

    st.markdown("#### Bandeja")
    if not notifs.empty:
        df_show = notifs.copy()
        df_show["estado"] = df_show["estado"].apply(chip_estado)
        df_show["prioridad"] = df_show["prioridad"].apply(chip_prioridad)
        st.dataframe(df_show.sort_values("ts_creacion", ascending=False), use_container_width=True)
    else:
        st.info("No hay notificaciones.")

    st.markdown("#### Actualizar estado")
    if not notifs.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            sel_id = st.number_input("ID de notificación", min_value=1, step=1, value=int(notifs["id"].min()))
        with col2:
            nuevo_estado = st.selectbox("Nuevo estado", ["Pendiente","Recibida","Completada"])
        with col3:
            evidencia = st.text_input("Evidencia (opcional)", value="")
        if st.button("Aplicar cambio"):
            mask = notifs["id"] == sel_id
            if mask.any():
                notifs.loc[mask, "estado"] = nuevo_estado
                if nuevo_estado == "Recibida":
                    notifs.loc[mask, "ts_recibida"] = now_iso()
                if nuevo_estado == "Completada":
                    notifs.loc[mask, "ts_cerrada"] = now_iso()
                if evidencia:
                    notifs.loc[mask, "evidencia"] = evidencia
                save_csv(notifs, F_NOTIF)
                st.cache_data.clear()
                st.success("Estado actualizado.")
            else:
                st.warning("ID no encontrado.")

# --------- RONDAS ---------
elif page == "Rondas":
    st.markdown("### 🔍 Rondas de inspección")
    if rondas_plt.empty:
        st.info("No hay plantillas de rondas.")
    else:
        plantillas = sorted(rondas_plt["plantilla"].unique())
        sel_pl = st.selectbox("Plantilla", plantillas)
        subset = rondas_plt[rondas_plt["plantilla"]==sel_pl].copy()
        operario = st.selectbox("Operario", usuarios["nombre"].tolist())

        st.markdown("#### Lecturas")
        rows = []
        for idx, r in subset.reset_index(drop=True).iterrows():
            col1, col2, col3, col4 = st.columns([2,2,2,2])
            with col1:
                st.text_input("Tag", r["tag"], key=f"tag_{idx}", disabled=True)
            with col2:
                st.text_input("Variable", r["variable"], key=f"var_{idx}", disabled=True)
            with col3:
                valor = st.number_input("Valor", key=f"val_{idx}",
                                        value=float((r["lim_inf"]+r["lim_sup"])/2))
            with col4:
                st.caption(f"Límites: [{r['lim_inf']}, {r['lim_sup']}]")
            en_rango = (r["lim_inf"] <= valor <= r["lim_sup"])
            rows.append({
                "id": next_sequential_id(rondas_run, "id") + idx,
                "ts": now_iso(), "plantilla": sel_pl, "tag": r["tag"],
                "variable": r["variable"], "valor": valor,
                "en_rango": en_rango, "operario": operario
            })

        if st.button("Guardar ronda", type="primary"):
            if rows:
                rondas_run = pd.concat([rondas_run, pd.DataFrame(rows)], ignore_index=True)
                save_csv(rondas_run, F_RONDAS_RUN)
                st.cache_data.clear()
                st.success("Ronda guardada.")

        st.markdown("#### Últimas ejecuciones")
        if not rondas_run.empty:
            st.dataframe(rondas_run.sort_values("ts", ascending=False).head(20), use_container_width=True)
        else:
            st.info("Aún no hay rondas ejecutadas.")

# --------- PTW / OT ---------
elif page == "PTW / OT":
    st.markdown("### 📝 Permisos de trabajo / Órdenes (demo)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tipo = st.selectbox("Tipo PTW", ["Trabajo caliente", "Espacio confinado", "Eléctrico", "Izaje"])
    with col2:
        solicitante = st.selectbox("Solicitante", usuarios["nombre"].tolist())
    with col3:
        area = st.selectbox("Área", activos["area"].unique())
    with col4:
        if st.button("Crear PTW", use_container_width=True, type="primary"):
            new_id = next_sequential_id(ptwot, "id")
            new_row = {
                "id": new_id, "ts_solicitud": now_iso(), "tipo": tipo,
                "solicitante": solicitante, "area": area, "estado": "Borrador",
                "aprob_hse": "No", "ts_cierre": "", "adjuntos": ""
            }
            ptwot = pd.concat([ptwot, pd.DataFrame([new_row])], ignore_index=True)
            save_csv(ptwot, F_PTWOT)
            st.cache_data.clear()
            st.success(f"PTW creado (ID {new_id}).")

    st.markdown("#### Bandeja PTW/OT")
    if not ptwot.empty:
        st.dataframe(ptwot.sort_values("ts_solicitud", ascending=False), use_container_width=True)
    else:
        st.info("Sin PTW/OT registrados.")

    st.markdown("#### Cambiar estado PTW")
    if not ptwot.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            idp = st.number_input("ID PTW", min_value=1, step=1, value=int(ptwot["id"].min()))
        with col2:
            nuevo = st.selectbox("Estado", ["Borrador","Aprobado","Cerrado"])
        with col3:
            aprob_hse = st.selectbox("Aprobación HSE", ["No","Sí"])
        if st.button("Aplicar"):
            mask = ptwot["id"] == idp
            if mask.any():
                ptwot.loc[mask, "estado"] = nuevo
                ptwot.loc[mask, "aprob_hse"] = aprob_hse
                if nuevo == "Cerrado":
                    ptwot.loc[mask, "ts_cierre"] = now_iso()
                save_csv(ptwot, F_PTWOT)
                st.cache_data.clear()
                st.success("PTW actualizado.")
            else:
                st.warning("ID no encontrado.")

# --------- INCIDENTES ---------
elif page == "Incidentes":
    st.markdown("### ⚠️ Incidentes / Near Miss (demo)")
    col1, col2, col3 = st.columns(3)
    with col1:
        tag = st.selectbox("Equipo", activos["tag"].unique())
        titulo = st.text_input("Título", value="Near Miss")
    with col2:
        severidad = st.selectbox("Severidad", ["Bajo","Medio","Alto","Crítico"], index=1)
        reportado_por = st.selectbox("Reportado por", usuarios["nombre"].tolist())
    with col3:
        descripcion = st.text_area("Descripción", height=100, value="Descripción breve del hecho.")

    if st.button("Reportar incidente", type="primary"):
        new_id = next_sequential_id(incidentes, "id")
        new_row = {
            "id": new_id, "ts": now_iso(), "tag": tag, "titulo": titulo,
            "severidad": severidad, "descripcion": descripcion,
            "reportado_por": reportado_por, "estado": "Abierto"
        }
        incidentes = pd.concat([incidentes, pd.DataFrame([new_row])], ignore_index=True)
        save_csv(incidentes, F_INCIDENTES)
        st.cache_data.clear()
        st.success(f"Incidente reportado (ID {new_id}).")

    st.markdown("#### Bandeja de incidentes")
    if not incidentes.empty:
        df_show = incidentes.copy()
        df_show["estado"] = df_show["estado"].apply(chip_estado)
        st.dataframe(df_show.sort_values("ts", ascending=False), use_container_width=True)
    else:
        st.info("Sin incidentes registrados.")

# --------- DASHBOARD ---------
elif page == "Dashboard":
    st.markdown("### 📊 Dashboard (demo)")
    c1, c2 = st.columns([1,2])

    with c1:
        st.markdown("#### KPIs")
        k_total = len(notifs) if not notifs.empty else 0
        k_p1 = int((notifs["prioridad"]=="P1").sum()) if not notifs.empty else 0
        k_comp = int((notifs["estado"]=="Completada").sum()) if not notifs.empty else 0
        k_inc = len(incidentes) if not incidentes.empty else 0
        st.metric("Notificaciones", k_total)
        st.metric("P1 activas", k_p1)
        st.metric("Completadas", k_comp)
        st.metric("Incidentes", k_inc)

    with c2:
        st.markdown("#### Distribución por estado")
        if not notifs.empty:
            cts = notifs["estado"].value_counts().reset_index()
            cts.columns = ["estado","cantidad"]
            fig = px.bar(cts, x="estado", y="cantidad")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de notificaciones.")

    st.markdown("#### Tendencias de rondas")
    if not rondas_run.empty:
        trend = (
            rondas_run.assign(date=lambda d: pd.to_datetime(d["ts"]).dt.date)
                      .groupby("date")["en_rango"].mean()
                      .reset_index()
        )
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=trend["date"], y=trend["en_rango"],
                                  mode="lines+markers", name="% en rango"))
        fig2.update_layout(yaxis_title="% en rango", xaxis_title="Fecha")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aún no hay rondas ejecutadas.")

# --------- DOCUMENTOS ---------
elif page == "Documentos":
    st.markdown("### 📚 Documentos (demo)")
    st.write("Biblioteca simple (P&ID, SOPs, permisos tipo).")
    st.info("Para el prototipo, podés poner PDFs en una carpeta /docs y listarlos aquí.")
    st.markdown("- **P&ID V-210** – Rev. B (placeholder)")
    st.markdown("- **SOP: Cambio de sello mecánico P-101** – Rev. A (placeholder)")
    st.markdown("- **Permiso tipo: Trabajo caliente** – Rev. C (placeholder)")

# --------- CONFIG & IoT ---------
elif page == "Config & IoT":
    st.markdown("### ⚙️ Config & IoT (simulador)")
    st.caption("Regla demo: si P > P_high en V-210 ⇒ crear notificación P1 asignada a Operación Área B")
    col1, col2, col3 = st.columns(3)
    with col1:
        p_actual = st.slider("Presión V-210 [bar]", 0.0, 50.0, 4.5, step=0.5)
    with col2:
        p_high = st.number_input("Umbral P_high [bar]", value=8.0, step=0.5)
    with col3:
        crear = st.button("Evaluar evento", type="primary")

    if crear:
        if p_actual > p_high:
            new_id = next_sequential_id(notifs, "id")
            new_row = {
                "id": new_id, "ts_creacion": now_iso(), "tag": "V-210",
                "titulo": "Alarma presión alta V-210", "motivo": f"P={p_actual} > {p_high}",
                "prioridad": "P1", "estado": "Pendiente", "asignado_a": "Operario 1",
                "ts_recibida": "", "ts_cerrada": "", "evidencia": "Evento IoT simulado"
            }
            notifs = pd.concat([notifs, pd.DataFrame([new_row])], ignore_index=True)
            save_csv(notifs, F_NOTIF)
            st.cache_data.clear()
            st.success(f"Notificación P1 creada por evento IoT (ID {new_id}).")
        else:
            st.info("No se dispara evento (P dentro de umbral).")

    st.divider()
    st.markdown("#### Gestión simple de usuarios (demo)")
    with st.form("form_user"):
        nombre = st.text_input("Nombre")
        rol = st.selectbox("Rol", ["Operario","Supervisor","HSE"])
        area = st.text_input("Área", value="Operación Área B")
        submitted = st.form_submit_button("Agregar")
        if submitted and nombre.strip():
            new_row = {"user_id": f"u{len(usuarios)+1}", "nombre": nombre, "rol": rol, "area": area}
            usuarios = pd.concat([usuarios, pd.DataFrame([new_row])], ignore_index=True)
            save_csv(usuarios, F_USUARIOS)
            st.cache_data.clear()
            st.success("Usuario agregado.")

    st.dataframe(usuarios, use_container_width=True)

# ======= Footer mini-diagnóstico =======
st.sidebar.caption(f"Build session: {datetime.now():%Y-%m-%d %H:%M}")
