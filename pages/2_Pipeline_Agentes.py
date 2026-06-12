"""Pipeline de Agentes Alegra — Interfaz web Streamlit."""
from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

import streamlit as st
from loguru import logger

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config as cfg_module  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402

# ── Session state ────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "pipe_running": False,
        "pipe_logs": [],
        "pipe_q": None,
        "pipe_result": None,
        "pipe_done": False,
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
                st.session_state.pipe_done = True
                st.session_state.pipe_result = item[1]
    except queue.Empty:
        pass

# ── Layout ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Pipeline Agentes", page_icon="⚙️", layout="wide")
st.title("⚙️ Pipeline de Agentes — Alegra")
st.caption(
    "7 fases secuenciales: valida primero (terceros, cuentas, balance) "
    "y solo sube a Alegra si todo está correcto."
)

col_left, col_right = st.columns([1, 2], gap="medium")

# ── Panel izquierdo: configuración y estado de fases ─────────────────────────

with col_left:
    st.subheader("Configuración")

    # Muestra las credenciales actuales del .env
    user_display = cfg_module.ALEGRA_USER or "⚠️ no configurado"
    with st.container(border=True):
        st.markdown(f"**Credenciales (.env)**  \nUsuario: `{user_display}`")
        if not cfg_module.ALEGRA_USER or not cfg_module.ALEGRA_TOKEN:
            st.error("Configura `ALEGRA_USER` y `ALEGRA_TOKEN` en el archivo `.env`")

    carpeta = st.text_input(
        "Carpeta de transacciones",
        value=str(cfg_module.TRANSACTIONS_FOLDER),
        help="Carpeta con los archivos xlsx/csv en formato estándar del pipeline",
    )

    st.divider()

    start_clicked = st.button(
        "▶ Ejecutar Pipeline",
        disabled=st.session_state.pipe_running or not cfg_module.ALEGRA_USER,
        type="primary",
        use_container_width=True,
    )

    if start_clicked:
        folder = Path(carpeta)
        if not folder.exists():
            st.error(f"Carpeta no encontrada: {carpeta}")
        else:
            files = (
                list(folder.glob("*.xlsx"))
                + list(folder.glob("*.xls"))
                + list(folder.glob("*.csv"))
            )
            if not files:
                st.error("No hay archivos xlsx/csv en la carpeta.")
            else:
                q: queue.Queue = queue.Queue()
                st.session_state.pipe_logs = []
                st.session_state.pipe_q = q
                st.session_state.pipe_running = True
                st.session_state.pipe_done = False
                st.session_state.pipe_result = None

                def _run_pipeline(qu: queue.Queue, folder_path: str):
                    # Sink de loguru que escribe a la cola
                    sink_id = logger.add(
                        lambda msg: qu.put(("log", msg.rstrip(), None)),
                        format="{time:HH:mm:ss} | {level:<8} | {message}",
                        colorize=False,
                        level="DEBUG",
                    )
                    try:
                        cfg_module.TRANSACTIONS_FOLDER = Path(folder_path)
                        orchestrator = Orchestrator()
                        result = orchestrator.run()
                    except Exception as e:
                        qu.put(("log", f"ERROR FATAL: {e}", None))
                        result = {"success": False, "phases": {}}
                    finally:
                        logger.remove(sink_id)
                    qu.put(("done", result, None))

                t = threading.Thread(
                    target=_run_pipeline, args=(q, carpeta), daemon=True
                )
                t.start()
                st.rerun()

    if st.session_state.pipe_running:
        st.info("Pipeline en ejecución...")

    # Limpiar
    if st.session_state.pipe_done and not st.session_state.pipe_running:
        if st.button("🗑 Nueva ejecución", use_container_width=True):
            st.session_state.pipe_logs = []
            st.session_state.pipe_done = False
            st.session_state.pipe_result = None
            st.rerun()

    # Resultado por fases
    if st.session_state.pipe_result:
        st.divider()
        st.subheader("Resultado por fase")

        result = st.session_state.pipe_result
        icons = {
            "OK":      "✅",
            "WARN":    "⚠️",
            "FAILED":  "❌",
            "BLOCKED": "🔒",
            "SKIPPED": "⏭️",
        }

        phases = result.get("phases", {})
        for key in sorted(phases):
            p = phases[key]
            icon = icons.get(p["status"], "?")
            color = (
                "green" if p["status"] == "OK"
                else "orange" if p["status"] == "WARN"
                else "red"
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

        # Estadísticas rápidas
        contacts_data = result.get("phases", {}).get("phase_3", {}).get("data") or {}
        coa_data      = result.get("phases", {}).get("phase_4", {}).get("data") or {}
        tpl_data      = result.get("phases", {}).get("phase_5", {}).get("data") or {}
        upload_data   = result.get("phases", {}).get("phase_7", {}).get("data") or {}

        if contacts_data:
            st.caption(
                f"Terceros: {contacts_data.get('total_required','?')} requeridos, "
                f"{contacts_data.get('created','?')} creados, "
                f"{len(contacts_data.get('failed',[]))} fallidos"
            )
        if tpl_data:
            st.caption(f"Filas en plantilla: {tpl_data.get('total_rows','?')}")
        if upload_data and isinstance(upload_data, dict):
            ids = upload_data.get("journal_entry_ids", [])
            if ids:
                st.caption(f"Comprobantes creados: {len(ids)}")

# ── Panel derecho: log en tiempo real ────────────────────────────────────────

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

# ── Rerun automático mientras corre ──────────────────────────────────────────

if st.session_state.pipe_running:
    time.sleep(0.4)
    st.rerun()
