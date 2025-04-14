
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
    df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
    df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
    df_minimos_raw = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")

    df_minimos_raw = df_minimos_raw.dropna(subset=["MES", "Codigo", "Cliente"])
    df_minimos_raw["MES"] = df_minimos_raw["MES"].astype(int)

    df_minimos = df_minimos_raw.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"].sum().to_frame()
    df_minimos["Pendiente"] = df_minimos["Minimo"]
    df_minimos_reset = df_minimos.reset_index()

    duplicados = df_minimos_reset.duplicated(subset=["MES", "Codigo", "Cliente"], keep=False)

    if duplicados.any():
        df_minimos_reset = df_minimos_reset.groupby(["MES", "Codigo", "Cliente"], as_index=False).agg({
            "Minimo": "sum",
            "Pendiente": "sum"
        })

    df_minimos = df_minimos_reset.set_index(["MES", "Codigo", "Cliente"]).sort_index()

    # Inicialización para simulación de df_asignacion
    clientes_ordenados = df_prioridad.index.tolist()
    df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

    for idx, fila in df_minimos.iterrows():
        mes, codigo, cliente = idx
        asignado = 1  # valor de prueba

        if (mes, codigo) not in df_asignacion.index:
            df_asignacion.loc[(mes, codigo), :] = 0

        if cliente not in df_asignacion.columns:
            df_asignacion[cliente] = 0

        df_asignacion.at[(mes, codigo), cliente] += asignado

    st.write("✅ Código ejecutado correctamente.")
