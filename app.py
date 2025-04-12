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
# Consolidar mínimos trasladados para evitar duplicaciones
df_minimos_reset = df_minimos_raw.reset_index()
df_minimos_reset["MES"] = df_minimos_reset["MES"].astype(int)

# Detectar duplicados por (Código, Cliente, MES)
duplicados = df_minimos_reset.duplicated(subset=["MES", "Codigo", "Cliente"], keep=False)

if duplicados.any():
    # Consolidar sumando mínimos y pendientes
    df_minimos_reset = df_minimos_reset.groupby(["MES", "Codigo", "Cliente"], as_index=False).agg({
        "Minimo": "sum",
        "Pendiente": "sum"
    })

# 3.1 - Restaurar MultiIndex y preparar df_minimos
df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
df_minimos_raw = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")

# Consolidar mínimos por (MES, Código, Cliente)
df_minimos_raw = df_minimos_raw.dropna(subset=["MES", "Codigo", "Cliente"])
df_minimos_raw["MES"] = df_minimos_raw["MES"].astype(int)

df_minimos = df_minimos_raw.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"].sum().to_frame()
df_minimos["Pendiente"] = df_minimos["Minimo"]
df_minimos_reset = df_minimos.reset_index()


# Consolidar resultados
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

# Exportar a Excel
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
    df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
    df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")
    resumen_clientes.to_excel(writer, sheet_name="Resumen Clientes")
output.seek(0)

# Descargar
st.success("✅ Optimización completada.")
st.download_button(
    label="📥 Descargar archivo Excel",
    data=output.getvalue(),
    file_name="asignacion_resultados_completo.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Gráficos
st.subheader("📊 Asignación Total por Cliente")
total_por_cliente = df_asignacion.sum().sort_values(ascending=False)
fig1, ax1 = plt.subplots(figsize=(10, 4))
sns.barplot(x=total_por_cliente.index, y=total_por_cliente.values, ax=ax1)
ax1.set_ylabel("Unidades Asignadas")
st.pyplot(fig1)

st.subheader("📊 Flujo Mensual de Stock")
df_stock_mes = df_stock_filtrado.reset_index().groupby("MES")[["Stock Disponible", "Stock Restante"]].sum()
df_stock_mes["Stock Asignado"] = df_stock_mes["Stock Disponible"] - df_stock_mes["Stock Restante"]
df_melted = df_stock_mes[["Stock Asignado", "Stock Restante"]].reset_index().melt(id_vars="MES", var_name="Tipo", value_name="Unidades")
fig2, ax2 = plt.subplots(figsize=(8, 4))
sns.barplot(data=df_melted, x="MES", y="Unidades", hue="Tipo", ax=ax2)
st.pyplot(fig2)

st.subheader("📈 Evolución de Asignación por Cliente")
df_cliente_mes = df_asignacion_reset.groupby(["MES", "Cliente"])["Asignado"].sum().reset_index()
fig3, ax3 = plt.subplots(figsize=(10, 5))
sns.lineplot(data=df_cliente_mes, x="MES", y="Asignado", hue="Cliente", marker="o", ax=ax3)
ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
st.pyplot(fig3)
