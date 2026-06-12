"""Migrador Siigo → Alegra — Interfaz web Streamlit."""
from __future__ import annotations

import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.migrador import Migrador  # noqa: E402

# ── Session state ────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "mig_running":  False,
        "mig_logs":     [],
        "mig_q":        None,
        "mig_stop":     None,
        "mig_progress": None,
        "mig_report":   None,
        "mig_done":     False,
        "mig_temp_dir": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()

# ── Drenado de cola ──────────────────────────────────────────────────────────

if st.session_state.mig_q is not None:
    try:
        while True:
            item = st.session_state.mig_q.get_nowait()
            kind = item[0]
            if kind == "log":
                st.session_state.mig_logs.append(item[1])
            elif kind == "prog":
                st.session_state.mig_progress = item[1]
            elif kind == "done":
                st.session_state.mig_running = False
                st.session_state.mig_done    = True
                st.session_state.mig_report  = item[1]
    except queue.Empty:
        pass

# ── Layout ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Migrador Alegra", page_icon="🔄", layout="wide")
st.title("🔄 Migrador Siigo → Alegra")
st.caption(
    "Sube los archivos AUXILIAR de Siigo y migralos a Alegra año por año. "
    "El checkpoint evita duplicar comprobantes si se interrumpe."
)

col_left, col_right = st.columns([1, 2], gap="medium")

# ── Panel izquierdo ──────────────────────────────────────────────────────────

with col_left:
    st.subheader("Configuración")

    email = st.text_input(
        "Email Alegra",
        placeholder="usuario@empresa.com",
        key="mig_email",
    )
    token = st.text_input(
        "Token API",
        type="password",
        placeholder="token de la API de Alegra",
        key="mig_token",
    )

    st.markdown("**Años a migrar**")
    YEARS = list(range(2017, 2026))
    cols3 = st.columns(3)
    year_vars: dict[int, bool] = {}
    for i, y in enumerate(YEARS):
        with cols3[i % 3]:
            year_vars[y] = st.checkbox(str(y), value=True, key=f"yr_{y}")

    st.divider()

    uploaded_files = st.file_uploader(
        "Archivos AUXILIAR (xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help=(
            "Sube los archivos exportados de Siigo. "
            "Deben llamarse **AUXILIAR XXXX.xlsx** donde XXXX es el año "
            "(p. ej. `AUXILIAR 2022.xlsx`)."
        ),
        disabled=st.session_state.mig_running,
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} archivo(s) cargado(s):")
        for f in uploaded_files:
            st.caption(f"  • {f.name}")

    st.divider()

    # Progreso
    if st.session_state.mig_progress:
        year_p, curr, total, ok, err, existing = st.session_state.mig_progress
        if year_p is not None and total:
            st.progress(curr / total, text=f"Año {year_p}: {curr:,} / {total:,}")
        m1, m2, m3 = st.columns(3)
        m1.metric("✓ Subidos",    f"{ok:,}")
        m2.metric("↺ Existentes", f"{existing:,}")
        m3.metric("✗ Errores",    f"{err:,}")

    b1, b2 = st.columns(2)
    with b1:
        start_clicked = st.button(
            "▶ Iniciar",
            disabled=st.session_state.mig_running,
            use_container_width=True,
            type="primary",
        )
    with b2:
        stop_clicked = st.button(
            "⏹ Detener",
            disabled=not st.session_state.mig_running,
            use_container_width=True,
        )

    # ── Iniciar migración ────────────────────────────────────────────────────

    if start_clicked:
        selected_years = [y for y, v in year_vars.items() if v]

        if not email or not token:
            st.error("Email y Token son requeridos.")
        elif not uploaded_files:
            st.error("Sube al menos un archivo AUXILIAR xlsx.")
        elif not selected_years:
            st.error("Selecciona al menos un año.")
        else:
            # Guardar archivos en directorio temporal de la sesión
            temp_dir = st.session_state.mig_temp_dir
            if temp_dir is None or not Path(temp_dir).exists():
                temp_dir = tempfile.mkdtemp(prefix="alegra_mig_")
                st.session_state.mig_temp_dir = temp_dir

            for f in uploaded_files:
                (Path(temp_dir) / f.name).write_bytes(f.getvalue())

            q: queue.Queue = queue.Queue()
            stop_event = threading.Event()

            st.session_state.mig_logs     = []
            st.session_state.mig_q        = q
            st.session_state.mig_stop     = stop_event
            st.session_state.mig_running  = True
            st.session_state.mig_done     = False
            st.session_state.mig_report   = None
            st.session_state.mig_progress = None

            migrador = Migrador(
                email=email,
                token=token,
                carpeta=temp_dir,
                years=selected_years,
                log_fn=lambda msg, tag=None: q.put(("log", msg, tag)),
                progress_fn=lambda yr, c, t, ok, er, ex=0: q.put(
                    ("prog", (yr, c, t, ok, er, ex), None)
                ),
                stop_event=stop_event,
            )

            def _run(m: Migrador, qu: queue.Queue):
                try:
                    report = m.run()
                except Exception as e:
                    qu.put(("log", f"ERROR FATAL: {e}", "err"))
                    report = None
                qu.put(("done", report, None))

            threading.Thread(target=_run, args=(migrador, q), daemon=True).start()
            st.rerun()

    if stop_clicked and st.session_state.mig_stop:
        st.session_state.mig_stop.set()
        st.warning("Señal de parada enviada.")

    # ── Resultado ────────────────────────────────────────────────────────────

    st.divider()
    if st.session_state.mig_done:
        report = st.session_state.mig_report
        if report and Path(report).exists():
            st.success("Migración completada.")
            with open(report, "rb") as f:
                st.download_button(
                    label="📊 Descargar Informe de Errores",
                    data=f.read(),
                    file_name=Path(report).name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        else:
            st.success("Migración completada — sin errores.")

    if st.session_state.mig_logs and not st.session_state.mig_running:
        if st.button("🗑 Limpiar", use_container_width=True):
            st.session_state.mig_logs     = []
            st.session_state.mig_done     = False
            st.session_state.mig_progress = None
            st.rerun()

# ── Panel derecho: log ───────────────────────────────────────────────────────

with col_right:
    st.subheader("Log en tiempo real")

    if st.session_state.mig_running:
        st.caption(":green[● EN CURSO]")
    elif st.session_state.mig_done:
        st.caption(":blue[● COMPLETADO]")
    else:
        st.caption(":gray[● EN ESPERA]")

    log_text = (
        "\n".join(st.session_state.mig_logs[-300:])
        if st.session_state.mig_logs
        else "Esperando inicio de migración..."
    )
    st.code(log_text, language=None)

# ── Rerun automático ─────────────────────────────────────────────────────────

if st.session_state.mig_running:
    time.sleep(0.4)
    st.rerun()
