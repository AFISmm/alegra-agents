"""Migrador Siigo → Alegra — Interfaz web Streamlit."""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from pathlib import Path

import streamlit as st

# Agrega la raíz del proyecto al path para poder importar utils, agents, etc.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.migrador import Migrador  # noqa: E402

# ── Configuración persistente ───────────────────────────────────────────────

CONFIG_PATH = _ROOT / ".portal_config.json"
YEARS = list(range(2017, 2026))


def load_config() -> dict:
    defaults = {"email": "", "token": "", "carpeta": "", "years": YEARS}
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── Session state ───────────────────────────────────────────────────────────

def _init():
    defaults = {
        "mig_running": False,
        "mig_logs": [],
        "mig_q": None,
        "mig_stop": None,
        "mig_progress": None,
        "mig_report": None,
        "mig_done": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()

# ── Drenado de la cola (ejecuta en cada rerun) ──────────────────────────────

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
                st.session_state.mig_done = True
                st.session_state.mig_report = item[1]
    except queue.Empty:
        pass

# ── Layout ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Migrador Alegra", page_icon="🔄", layout="wide")
st.title("🔄 Migrador Siigo → Alegra")
st.caption(
    "Sube comprobantes contables del Libro Auxiliar de Siigo a Alegra, "
    "año por año. Retoma donde se quedó gracias al checkpoint."
)

cfg = load_config()
col_left, col_right = st.columns([1, 2], gap="medium")

# ── Panel izquierdo: configuración y controles ──────────────────────────────

with col_left:
    st.subheader("Configuración")

    with st.form("mig_config_form"):
        email = st.text_input(
            "Email Alegra",
            value=cfg["email"],
            placeholder="usuario@empresa.com",
        )
        token = st.text_input(
            "Token API",
            value=cfg["token"],
            type="password",
            placeholder="token de Alegra",
        )
        carpeta = st.text_input(
            "Carpeta con archivos AUXILIAR",
            value=cfg["carpeta"],
            placeholder="Ruta completa a la carpeta",
            help="Debe contener archivos AUXILIAR XXXX.xlsx (uno por año)",
        )

        st.markdown("**Años a migrar**")
        saved_years = set(cfg.get("years", YEARS))
        year_vars: dict[int, bool] = {}
        cols = st.columns(3)
        for i, y in enumerate(YEARS):
            with cols[i % 3]:
                year_vars[y] = st.checkbox(str(y), value=(y in saved_years), key=f"yr_{y}")

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        # Botones de selección rápida dentro del form no son interactivos entre sí,
        # por eso solo está el submit principal aquí.
        save_btn = st.form_submit_button("💾 Guardar configuración", use_container_width=True)

    if save_btn:
        selected = [y for y, v in year_vars.items() if v]
        save_config({"email": email, "token": token, "carpeta": carpeta, "years": selected})
        st.success("Configuración guardada.")

    st.divider()

    # Métricas de progreso
    if st.session_state.mig_progress:
        year_p, curr, total, ok, err, existing = st.session_state.mig_progress
        if year_p is not None:
            pct = curr / total if total else 0
            st.progress(pct, text=f"Año {year_p}: {curr:,} / {total:,} comprobantes")
        m1, m2, m3 = st.columns(3)
        m1.metric("✓ Subidos", f"{ok:,}")
        m2.metric("↺ Existentes", f"{existing:,}")
        m3.metric("✗ Errores", f"{err:,}")

    # Botones de acción
    st.markdown("")
    b1, b2 = st.columns(2)

    selected_years = [y for y, v in year_vars.items() if v]

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

    # Acción: iniciar migración
    if start_clicked:
        if not email or not token:
            st.error("Email y Token son requeridos.")
        elif not carpeta or not Path(carpeta).exists():
            st.error("La carpeta especificada no existe.")
        elif not selected_years:
            st.error("Selecciona al menos un año.")
        else:
            save_config({"email": email, "token": token, "carpeta": carpeta, "years": selected_years})

            q: queue.Queue = queue.Queue()
            stop_event = threading.Event()

            st.session_state.mig_logs = []
            st.session_state.mig_q = q
            st.session_state.mig_stop = stop_event
            st.session_state.mig_running = True
            st.session_state.mig_done = False
            st.session_state.mig_report = None
            st.session_state.mig_progress = None

            migrador = Migrador(
                email=email,
                token=token,
                carpeta=carpeta,
                years=selected_years,
                log_fn=lambda msg, tag=None: q.put(("log", msg, tag)),
                progress_fn=lambda yr, c, t, ok, er, ex=0: q.put(
                    ("prog", (yr, c, t, ok, er, ex), None)
                ),
                stop_event=stop_event,
            )

            def _run_thread(m: Migrador, qu: queue.Queue):
                try:
                    report = m.run()
                except Exception as e:
                    qu.put(("log", f"ERROR FATAL: {e}", "err"))
                    report = None
                qu.put(("done", report, None))

            t = threading.Thread(target=_run_thread, args=(migrador, q), daemon=True)
            t.start()
            st.rerun()

    # Acción: detener
    if stop_clicked and st.session_state.mig_stop:
        st.session_state.mig_stop.set()
        st.warning("Enviando señal de parada...")

    # Botón de descarga del informe
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
            st.success("Migración completada — sin errores, no se generó informe.")

    # Botón para limpiar log
    if st.session_state.mig_logs and not st.session_state.mig_running:
        if st.button("🗑 Limpiar log", use_container_width=True):
            st.session_state.mig_logs = []
            st.session_state.mig_done = False
            st.session_state.mig_progress = None
            st.rerun()

# ── Panel derecho: log en tiempo real ───────────────────────────────────────

with col_right:
    st.subheader("Log en tiempo real")

    running_badge = ":green[● EN CURSO]" if st.session_state.mig_running else (
        ":red[● DETENIDO]" if st.session_state.mig_done and st.session_state.mig_report is None
        and not (st.session_state.mig_report)
        else ":gray[● EN ESPERA]"
    )
    if st.session_state.mig_done:
        running_badge = ":green[● COMPLETADO]"

    st.caption(running_badge)

    log_text = (
        "\n".join(st.session_state.mig_logs[-300:])
        if st.session_state.mig_logs
        else "Esperando inicio de migración..."
    )
    st.code(log_text, language=None)

# ── Rerun automático mientras corre ─────────────────────────────────────────

if st.session_state.mig_running:
    time.sleep(0.4)
    st.rerun()
