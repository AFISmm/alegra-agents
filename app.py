"""Portal de Migración Alegra — Mercury Methods."""
import streamlit as st

st.set_page_config(
    page_title="Portal Alegra — Mercury Methods",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Portal de Migración Alegra")
st.markdown("**Mercury Methods** · Herramientas para migración de datos contables a Alegra.")

st.divider()

col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.subheader("🔄 Migrador Siigo → Alegra")
        st.markdown("""
Migra comprobantes contables del **Libro Auxiliar de Siigo** a Alegra,
año por año, con checkpoint para retomar donde se quedó.

**Características:**
- Selección de años (2017–2025)
- Crea cuentas PUC y contactos automáticamente si no existen
- Checkpoint: retoma donde se interrumpió sin duplicar
- Informe Excel de errores y comprobantes ya existentes
        """)
        st.info("Navega a **Migrador Alegra** en el menú lateral para comenzar.")

with col2:
    with st.container(border=True):
        st.subheader("⚙️ Pipeline de Agentes")
        st.markdown("""
Pipeline de **7 fases** que valida todo antes de subir:

1. Verificación de conexión API
2. Lectura y validación de transacciones
3. Sincronización de terceros (crea los faltantes)
4. Verificación del plan de cuentas
5. Generación de plantilla CSV Alegra
6. Gate de seguridad pre-carga
7. Carga masiva con fallback individual por comprobante
        """)
        st.info("Navega a **Pipeline Agentes** en el menú lateral para comenzar.")

st.divider()

with st.expander("¿Cuál herramienta usar?"):
    st.markdown("""
| Situación | Herramienta recomendada |
|---|---|
| Migración histórica de múltiples años (Siigo → Alegra) | **Migrador Alegra** |
| Subir archivos con formato estándar ya preparados | **Pipeline Agentes** |
| Primera vez: no sabes si las cuentas y contactos existen | **Migrador Alegra** (los crea automáticamente) |
| Quieres validar antes de tocar Alegra | **Pipeline Agentes** (gate pre-carga) |
    """)

st.caption("Para iniciar: `streamlit run app.py` desde la carpeta `alegra_agents/`")
