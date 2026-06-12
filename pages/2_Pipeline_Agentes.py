"""Pipeline de Agentes Alegra — Interfaz web Streamlit."""
from __future__ import annotations

import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st
from loguru import logger

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.orchestrator import Orchestrator  # noqa: E402
import config as cfg_module                   # noqa: E402

# ── Session state ────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "pipe_running":  False,
        "pipe_logs":     [],
        "pipe_q":        None,
        "pipe_result":   None,
        "pipe_done":     False,
        "pipe_temp_dir": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()

# ── Drenado de cola ──────────────────────────────────────────────────────────

if st.session_state.pipe_q is not None:
    try:
        while True:
            item = st.session_state.pipe_q.get_nowait()
            if item[0] == "log":
                st.session_state.pipe_logs.append(item[1])
            elif item[0] == "done":
                st.session_state.pipe_running = False
                st.session_state.pipe_done    = True
                st.session_state.pipe_result  = item[1]
    except queue.Empty:
        pass

# ── Layout ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Pipeline Agentes", page_icon="⚙️", layout="wide")
st.title("⚙️ Pipeline de Agentes — Alegra")
st.caption(
    "7 fases secuenciales: valida terceros, plan de cuentas y balance "
    "antes de subir nada a Alegra."
)

col_left, col_right = st.columns([1, 2], gap="medium")

# ── Panel izquierdo ──────────────────────────────────────────────────────────

with col_left:
    st.subheader("Configuración")

    # Credenciales — primero intenta Streamlit Secrets, luego .env, luego vacío
    _secrets_user  = st.secrets.get("ALEGRA_USER",  "") if hasattr(st, "secrets") else ""
    _secrets_token = st.secrets.get("ALEGRA_TOKEN", "") if hasattr(st, "secrets") else ""
    _default_user  = _secrets_user  or cfg_module.ALEGRA_USER  or ""
    _default_token = _secrets_token or cfg_module.ALEGRA_TOKEN or ""

    email = st.text_input(
        "Email Alegra",
        value=_default_user,
        placeholder="usuario@empresa.com",
        key="pipe_email",
    )
    token = st.text_input(
        "Token API",
        value=_default_token,
        type="password",
        placeholder="token de la API de Alegra",
        key="pipe_token",
    )

    st.divider()

    uploaded_files = st.file_uploader(
        "Archivos de transacciones",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help=(
            "Sube los archivos en formato estándar del pipeline "
            "(xlsx/csv con columnas: fecha, nit_tercero, codigo_cuenta, debito, credito…). "
            "También acepta Libros Auxiliares de Siigo directamente."
        ),
        disabled=st.session_state.pipe_running,
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} archivo(s) cargado(s):")
        for f in uploaded_files:
            st.caption(f"  • {f.name}")

    st.divider()

    start_clicked = st.button(
        "▶ Ejecutar Pipeline",
        disabled=st.session_state.pipe_running,
        type="primary",
        use_container_width=True,
    )

    if start_clicked:
        if not email or not token:
            st.error("Email y Token son requeridos.")
        elif not uploaded_files:
            st.error("Sube al menos un archivo de transacciones.")
        else:
            # Guardar archivos en directorio temporal
            temp_dir = st.session_state.pipe_temp_dir
            if temp_dir is None or not Path(temp_dir).exists():
                temp_dir = tempfile.mkdtemp(prefix="alegra_pipe_")
                st.session_state.pipe_temp_dir = temp_dir

            for f in uploaded_files:
                (Path(temp_dir) / f.name).write_bytes(f.getvalue())

            q: queue.Queue = queue.Queue()
            st.session_state.pipe_logs    = []
            st.session_state.pipe_q       = q
            st.session_state.pipe_running = True
            st.session_state.pipe_done    = False
            st.session_state.pipe_result  = None

            def _run_pipeline(qu: queue.Queue, folder: str, usr: str, tkn: str):
                import os
                os.environ["ALEGRA_USER"]  = usr
                os.environ["ALEGRA_TOKEN"] = tkn

                # Recargar config con las nuevas variables de entorno
                cfg_module.ALEGRA_USER  = usr
                cfg_module.ALEGRA_TOKEN = tkn
                cfg_module.TRANSACTIONS_FOLDER = Path(folder)

                sink_id = logger.add(
                    lambda msg: qu.put(("log", msg.rstrip(), None)),
                    format="{time:HH:mm:ss} | {level:<8} | {message}",
                    colorize=False,
                    level="DEBUG",
                )
                try:
                    orchestrator = Orchestrator()
                    result = orchestrator.run()
                except Exception as e:
                    qu.put(("log", f"ERROR FATAL: {e}", None))
                    result = {"success": False, "phases": {}}
                finally:
                    logger.remove(sink_id)
                qu.put(("done", result, None))

            threading.Thread(
                target=_run_pipeline,
                args=(q, temp_dir, email, token),
                daemon=True,
            ).start()
            st.rerun()

    if st.session_state.pipe_running:
        st.info("Pipeline en ejecución...")

    if st.session_state.pipe_done and not st.session_state.pipe_running:
        if st.button("🗑 Nueva ejecución", use_container_width=True):
            st.session_state.pipe_logs   = []
            st.session_state.pipe_done   = False
            st.session_state.pipe_result = None
            st.rerun()

    # ── Resultado por fase ───────────────────────────────────────────────────

    if st.session_state.pipe_result:
        st.divider()
        st.subheader("Resultado por fase")

        result = st.session_state.pipe_result
        icons  = {
            "OK": "✅", "WARN": "⚠️", "FAILED": "❌",
            "BLOCKED": "🔒", "SKIPPED": "⏭️",
        }
        phases = result.get("phases", {})
        for key in sorted(phases):
            p    = phases[key]
            icon = icons.get(p["status"], "?")
            color = (
                "green"  if p["status"] == "OK"   else
                "orange" if p["status"] == "WARN"  else
                "red"
            )
            st.markdown(
                f"{icon} **Fase {p['phase']}: {p['name']}**  \n"
                f":{color}[{p['status']}] — `{p['elapsed_s']}s`"
            )
            if p.get("error"):
                st.caption(f"↳ {p['error']}")

        st.divider()
        if result.get("success"):
            st.success("Pipeline completado exitosamente.")
        else:
            st.error("Pipeline completado con errores. Revisa el log.")

        # Estadísticas
        contacts = result.get("phases", {}).get("phase_3", {}).get("data") or {}
        tpl      = result.get("phases", {}).get("phase_5", {}).get("data") or {}
        upload   = result.get("phases", {}).get("phase_7", {}).get("data") or {}

        if contacts:
            st.caption(
                f"Terceros: {contacts.get('total_required','?')} requeridos, "
                f"{contacts.get('created','?')} creados, "
                f"{len(contacts.get('failed',[]))} fallidos"
            )
        if tpl:
            st.caption(f"Filas en plantilla: {tpl.get('total_rows','?')}")
        if upload and isinstance(upload, dict):
            ids = upload.get("journal_entry_ids", [])
            if ids:
                st.caption(f"Comprobantes creados: {len(ids)}")

# ── Panel derecho: log ───────────────────────────────────────────────────────

with col_right:
    st.subheader("Log en tiempo real")

    if st.session_state.pipe_running:
        st.caption(":green[● EN CURSO]")
    elif st.session_state.pipe_done:
        st.caption(":blue[● COMPLETADO]")
    else:
        st.caption(":gray[● EN ESPERA]")

    log_text = (
        "\n".join(st.session_state.pipe_logs[-300:])
        if st.session_state.pipe_logs
        else "Esperando ejecución del pipeline..."
    )
    st.code(log_text, language=None)

# ── Rerun automático ─────────────────────────────────────────────────────────

if st.session_state.pipe_running:
    time.sleep(0.4)
    st.rerun()
