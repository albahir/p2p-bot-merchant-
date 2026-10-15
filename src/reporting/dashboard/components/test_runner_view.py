"""Componente para ejecución visual de pruebas automatizadas (pytest)."""

import io
import sys

import pytest
import streamlit as st


def render_test_runner():
    """Ejecutor interactivo de pruebas unitarias y de integración."""
    st.subheader(":material/science: Ejecutor Visual de Pruebas")
    st.caption("Verifica el cumplimiento de los contratos de seguridad, motor fiscal y conector sin usar la terminal.")

    with st.container(border=True):
        st.write("Haz clic para correr todos los tests automatizados de la suite `tests/`:")
        if st.button("Ejecutar Suite de Pruebas (Pytest)", width="stretch"):
            with st.spinner("Ejecutando pruebas automatizadas..."):
                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                try:
                    exit_code = pytest.main(["-v", "tests/"])
                finally:
                    sys.stdout = old_stdout
                output = buffer.getvalue()

            if exit_code == 0:
                st.success("¡Todos los tests pasaron exitosamente! (100% verde)")
            else:
                st.error("Se detectaron fallos en la suite de pruebas.")

            with st.expander("Ver salida detallada de ejecución"):
                st.code(output, language="text")
