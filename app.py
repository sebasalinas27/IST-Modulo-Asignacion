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

    clientes_ordenados = df_prioridad.sort_values(by=df_prioridad.columns[0]).index.tolist()
    meses_ordenados = sorted(df_stock["MES"].unique())

    df_stock_filtrado = df_stock[df_stock["Stock Disponible"] > 0].copy()
    df_stock_filtrado = df_stock_filtrado.set_index(["MES", "Codigo"]).sort_index()
    df_stock_filtrado["Stock Restante"] = df_stock_filtrado["Stock Disponible"]

    df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)
    minimos_agregados = set()

    for mes in meses_ordenados:
        if mes > 1:
            stock_ant = df_stock_filtrado.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
            for codigo, valor in stock_ant.items():
                if (mes, codigo) in df_stock_filtrado.index:
                    df_stock_filtrado.loc[(mes, codigo), "Stock Disponible"] += valor
                    df_stock_filtrado.loc[(mes, codigo), "Stock Restante"] += valor

        for cliente in clientes_ordenados:
            pendientes_cliente = df_minimos.loc[
                (df_minimos.index.get_level_values(0) <= mes) &
                (df_minimos.index.get_level_values(2) == cliente)
            ]
            pendientes_cliente = pendientes_cliente[pendientes_cliente["Pendiente"] > 0]

            for idx, fila in pendientes_cliente.iterrows():
                m_origen, codigo, cli = idx
                idx_actual = (mes, codigo, cliente)

                if (mes, codigo) not in df_stock_filtrado.index:
                    continue

                if idx_actual not in df_minimos.index and idx_actual not in minimos_agregados:
                    df_minimos.loc[idx_actual] = [0, 0]
                    minimos_agregados.add(idx_actual)

                stock_disp = df_stock_filtrado.loc[(mes, codigo), "Stock Restante"]
                pendiente = fila["Pendiente"]

                if pendiente > 0 and stock_disp > 0:
                    asignado = min(pendiente, stock_disp)
                    df_asignacion.at[(mes, codigo), cliente] += asignado
                    df_stock_filtrado.at[(mes, codigo), "Stock Restante"] -= asignado
                    df_minimos.loc[idx, "Pendiente"] -= asignado

    df_asignacion_reset = df_asignacion.reset_index().melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
    asignado_total = df_asignacion_reset.groupby(["MES", "Codigo", "Cliente"])["Asignado"].sum()
    asignado_total.index.names = ["MES", "Codigo", "Cliente"]

    minimos_check = df_minimos.copy()
    minimos_check["Asignado"] = asignado_total.reindex(minimos_check.index, fill_value=0).astype(float)
    minimos_check["Cumple"] = minimos_check["Asignado"] >= minimos_check["Minimo"]
    minimos_check["Pendiente Final"] = minimos_check["Minimo"] - minimos_check["Asignado"]

    minimos_pos = minimos_check[minimos_check["Minimo"] > 0].copy()
    resumen_clientes = minimos_pos.groupby("Cliente").agg(
        Total_Minimo=("Minimo", "sum"),
        Total_Asignado=("Asignado", "sum")
    )
    resumen_clientes["% Cumplido"] = (resumen_clientes["Total_Asignado"] / resumen_clientes["Total_Minimo"] * 100).round(2)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
        df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
        df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
        df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")
        resumen_clientes.to_excel(writer, sheet_name="Resumen Clientes")
    output.seek(0)

    st.success("✅ Optimización completada.")
    st.download_button(
        label="📥 Descargar archivo Excel",
        data=output.getvalue(),
        file_name="asignacion_resultados_completo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
