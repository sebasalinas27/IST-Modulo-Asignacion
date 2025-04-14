import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes")

st.markdown("""
Sube tu archivo Excel con las siguientes hojas:
- `Stock Disponible`
- `Mínimos de Asignación`
- `Prioridad Clientes`

---
📥 ¿No tienes un archivo?  
👉 [Descargar archivo de prueba](https://github.com/sebasalinas27/IST-Modulo-Asignacion/raw/main/Template_Pruebas_PIAT.xlsx)
""")

uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

with st.expander("ℹ️ ¿Cómo interpretar el archivo descargado?"):
    st.markdown("""
    El archivo contiene:

    📄 Asignación Óptima → unidades por código, mes y cliente.  
    📄 Stock Disponible → stock inicial, restante y arrastrado.  
    📄 Resumen Clientes → % de cumplimiento por cliente.
    """)

with st.expander("❗ Tips para evitar errores"):
    st.markdown("""
    - Usa nombres exactos en las hojas  
    - Elimina filtros, fórmulas y filas vacías  
    - Solo formato `.xlsx`
    """)

if uploaded_file:
    try:
        # Carga de datos
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos_raw = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")

        df_stock = df_stock[df_stock['Stock Disponible'] > 0].copy()
        df_stock['MES'] = df_stock['MES'].astype(int)
        df_stock = df_stock.set_index(['MES', 'Codigo']).sort_index()
        df_stock['Stock Restante'] = df_stock['Stock Disponible']

        df_minimos_raw = df_minimos_raw.dropna(subset=["MES", "Codigo", "Cliente"])
        df_minimos_raw["MES"] = df_minimos_raw["MES"].astype(int)

        df_minimos = df_minimos_raw.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"].sum().to_frame()
        df_minimos["Pendiente"] = df_minimos["Minimo"]

        df_minimos_reset = df_minimos.reset_index()
        duplicados = df_minimos_reset.duplicated(subset=["MES", "Codigo", "Cliente"], keep=False)

        if duplicados.any():
            df_minimos_reset = df_minimos_reset.groupby(["MES", "Codigo", "Cliente"], as_index=False).agg({
                "Minimo": "sum", "Pendiente": "sum"
            })

        df_minimos = df_minimos_reset.set_index(["MES", "Codigo", "Cliente"]).sort_index()

        # Mostrar resumen
        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock.index.get_level_values(1).nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock.index.get_level_values(0).nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            clientes_ordenados = df_prioridad.iloc[:, 0].sort_values().index.tolist()
            index_completo = pd.MultiIndex.from_product(
                [df_stock.index.get_level_values(0).unique(), df_stock.index.get_level_values(1).unique()],
                names=["MES", "Codigo"]
            )
            df_asignacion = pd.DataFrame(0, index=index_completo, columns=clientes_ordenados)

            for idx, fila in df_minimos.iterrows():
                mes, codigo, cliente = idx
                if (mes, codigo) in df_stock.index:
                    stock_disp = df_stock.at[(mes, codigo), 'Stock Restante']
                    asignado = min(fila["Pendiente"], stock_disp)
                    df_asignacion.at[(mes, codigo), cliente] += asignado
                    df_stock.at[(mes, codigo), 'Stock Restante'] -= asignado
                    df_minimos.at[idx, "Pendiente"] -= asignado

            df_asignacion_reset = df_asignacion.reset_index().melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
            asignado_total = df_asignacion_reset.groupby(["MES", "Codigo", "Cliente"])["Asignado"].sum()
            asignado_total.index.names = ["MES", "Codigo", "Cliente"]

            minimos_check = df_minimos.copy()
            minimos_check["Asignado"] = asignado_total.reindex(minimos_check.index, fill_value=0).astype(float)
            minimos_check["Cumple"] = minimos_check["Asignado"] >= minimos_check["Minimo"]
            minimos_check["Pendiente Final"] = minimos_check["Minimo"] - minimos_check["Asignado"]

            resumen_clientes = minimos_check.groupby("Cliente").agg(
                Total_Minimo=("Minimo", "sum"),
                Total_Asignado=("Asignado", "sum")
            )
            resumen_clientes["% Cumplido"] = (resumen_clientes["Total_Asignado"] / resumen_clientes["Total_Minimo"] * 100).round(2)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock.to_excel(writer, sheet_name="Stock Disponible")
                df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")
                resumen_clientes.to_excel(writer, sheet_name="Resumen Clientes")
            output.seek(0)

            st.success("✅ Código ejecutado correctamente.")
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_completo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {str(e)}")
