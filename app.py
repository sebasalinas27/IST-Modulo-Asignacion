# PIAT v1.3 - Asignación con pendientes arrastrables, cliente PUSH y validación completa
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
 
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.3)")
 
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
 
if uploaded_file:
    try:
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])
 
        df_minimos = df_minimos.groupby(level=[0, 1, 2]).sum().sort_index()
        df_minimos["Pendiente"] = df_minimos["Minimo"]
 
        prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(5)
        clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
 
        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")
 
        if st.button("🔁 Ejecutar Asignación"):
            df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()
            df_stock = df_stock.set_index(["MES", "Codigo"]).sort_index()
            df_stock["Stock Restante"] = df_stock["Stock Disponible"]
 
            codigos_validos = set(df_stock.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
            df_stock = df_stock[df_stock.index.get_level_values(1).isin(codigos_validos)]
            df_minimos = df_minimos[df_minimos.index.get_level_values(1).isin(codigos_validos)]
 
            meses = sorted(df_stock.index.get_level_values(0).unique())
            df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados + ["PUSH"])
            minimos_agregados = set()
 
            for mes in meses:
                if mes > 1:
                    stock_ant = df_stock.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock.index:
                            df_stock.loc[(mes, codigo), "Stock Disponible"] += valor
                            df_stock.loc[(mes, codigo), "Stock Restante"] += valor
 
                for cliente in clientes_ordenados:
                    pendientes = df_minimos[(df_minimos.index.get_level_values(0) <= mes) & 
                                            (df_minimos.index.get_level_values(2) == cliente)]
                    pendientes = pendientes[pendientes["Pendiente"] > 0]
 
                    for idx, fila in pendientes.iterrows():
                        m_orig, codigo, cli = idx
                        if (mes, codigo) not in df_stock.index:
                            continue
 
                        idx_actual = (mes, codigo, cliente)
                        if idx_actual not in df_minimos.index and idx_actual not in minimos_agregados:
                            df_minimos.loc[idx_actual] = [0, 0, 0]
                            minimos_agregados.add(idx_actual)
 
                        stock_disp = df_stock.loc[(mes, codigo), "Stock Restante"]
                        pendiente = fila["Pendiente"]
 
                        if pendiente > 0 and stock_disp > 0:
                            asignado = min(pendiente, stock_disp)
                            df_asignacion.at[(mes, codigo), cliente] += asignado
                            df_stock.loc[(mes, codigo), "Stock Restante"] -= asignado
                            df_minimos.loc[idx, "Pendiente"] -= asignado
 
                # Asignar restante a PUSH
                for (mes_c, codigo), fila_stock in df_stock.loc[mes].iterrows():
                    restante = fila_stock["Stock Restante"]
                    if restante > 0:
                        df_asignacion.at[(mes, codigo), "PUSH"] += restante
                        df_stock.loc[(mes, codigo), "Stock Restante"] = 0
 
            # Generar resumen
            df_minimos["Asignado"] = df_minimos.index.map(lambda x: df_asignacion.at[(x[0], x[1]), x[2]] if (x[0], x[1]) in df_asignacion.index else 0)
            df_minimos["Cumple"] = df_minimos["Asignado"] >= df_minimos["Minimo"]
            df_minimos["Pendiente Final"] = df_minimos["Minimo"] - df_minimos["Asignado"]
 
            resumen = df_minimos[df_minimos["Minimo"] > 0].groupby("Cliente").agg(
                Total_Minimo=("Minimo", "sum"),
                Total_Asignado=("Asignado", "sum")
            )
            resumen["% Cumplido"] = (resumen["Total_Asignado"] / resumen["Total_Minimo"] * 100).round(2)
 
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock.reset_index().to_excel(writer, sheet_name="Stock Disponible", index=False)
                df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                df_minimos.reset_index().to_excel(writer, sheet_name="Mínimos de Asignación", index=False)
                resumen.reset_index().to_excel(writer, sheet_name="Resumen Clientes", index=False)
            output.seek(0)
 
            st.success("✅ Optimización completada.")
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_PIAT_v1_3.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
 
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
