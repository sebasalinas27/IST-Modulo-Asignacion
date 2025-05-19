import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
import traceback

st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.5 Prioridad Fix + Flujo continuo)")

st.markdown("""
### ✅ ¿Qué hace este módulo?

- Asigna productos considerando **mínimos requeridos por cliente y mes**
- Utiliza el **stock restante como flujo acumulado entre meses**
- Prioriza clientes por nivel definido (1 es mayor prioridad)
- El stock sobrante **se arrastra como flujo**, no se manda a `PUSH`
- Exporta un archivo Excel con todas las vistas necesarias

---
📥 ¿No tienes un archivo?  
👉 Descargar archivo de prueba
""")

uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# --- Funciones ---

def cargar_datos(uploaded_file):
    df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
    df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
    df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])
    return df_stock, df_prioridad, df_minimos

def preprocesar_datos(df_stock, df_prioridad, df_minimos):
    df_minimos = df_minimos.groupby(level=[0, 1, 2]).sum().sort_index()
    df_minimos["Pendiente"] = df_minimos["Minimo"]

    prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(5)
    clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

    df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()
    df_stock = df_stock.set_index(["MES", "Codigo"]).sort_index()
    df_stock["Stock Restante"] = df_stock["Stock Disponible"]

    codigos_validos = set(df_stock.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
    df_stock = df_stock[df_stock.index.get_level_values(1).isin(codigos_validos)]
    df_minimos = df_minimos[df_minimos.index.get_level_values(1).isin(codigos_validos)]

    return df_stock, df_prioridad, df_minimos, prioridad_clientes, clientes_ordenados

def asignar_stock(df_stock, df_minimos, prioridad_clientes, clientes_ordenados):
    meses = sorted(df_stock.index.get_level_values(0).unique())
    df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)
    stock_flujo = {}

    for mes in meses:
        for codigo in df_stock.index.get_level_values(1).unique():
            if (mes, codigo) in df_stock.index:
                disponible = df_stock.at[(mes, codigo), "Stock Restante"]
                stock_flujo[codigo] = stock_flujo.get(codigo, 0) + disponible

        pendientes_mes = df_minimos[(df_minimos.index.get_level_values(0) == mes)]
        pendientes_mes = pendientes_mes[pendientes_mes["Pendiente"] > 0].reset_index()
        pendientes_mes["Prioridad"] = pendientes_mes["Cliente"].map(prioridad_clientes)
        pendientes_mes = pendientes_mes.sort_values(by="Prioridad")

        for _, fila in pendientes_mes.iterrows():
            m, codigo, cliente = fila["MES"], fila["Codigo"], fila["Cliente"]
            pendiente = df_minimos.at[(m, codigo, cliente), "Pendiente"]
            disponible = stock_flujo.get(codigo, 0)

            if pendiente > 0 and disponible > 0:
                asignado = min(pendiente, disponible)
                if (mes, codigo) not in df_asignacion.index:
                    df_asignacion.loc[(mes, codigo), :] = 0
                df_asignacion.at[(mes, codigo), cliente] += asignado
                df_minimos.at[(m, codigo, cliente), "Pendiente"] -= asignado
                stock_flujo[codigo] -= asignado

    return df_asignacion, df_minimos

def calcular_resultados(df_asignacion, df_minimos):
    df_minimos["Asignado"] = df_minimos.index.map(
        lambda x: df_asignacion.at[(x[0], x[1]), x[2]] if (x[0], x[1]) in df_asignacion.index else 0
    )
    df_minimos["Cumple"] = df_minimos["Asignado"] >= df_minimos["Minimo"]
    df_minimos["Pendiente Final"] = df_minimos["Minimo"] - df_minimos["Asignado"]
    return df_minimos

def exportar_excel(df_asignacion, df_stock, df_prioridad, df_minimos):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_asignacion.to_excel(writer, sheet_name="Asignación Flujo")
        df_stock.reset_index().to_excel(writer, sheet_name="Stock Disponible", index=False)
        df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
        df_minimos.reset_index().to_excel(writer, sheet_name="Mínimos de Asignación", index=False)
    output.seek(0)
    return output

# --- Ejecución principal ---

if uploaded_file:
    st.subheader("📊 Resumen del archivo cargado")
    df_stock_preview = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
    df_prioridad_preview = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes")
    df_minimos_preview = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")

    st.write(f"- **Productos**: {df_stock_preview['Codigo'].nunique()}")
    st.write(f"- **Clientes**: {df_prioridad_preview.shape[0]}")
    st.write(f"- **Meses**: {df_stock_preview['MES'].nunique()}")
    st.write(f"- **Celdas con mínimo asignado**: {(df_minimos_preview['Minimo'] > 0).sum()}")

    if st.button("🔁 Ejecutar Asignación"):
        try:
            df_stock, df_prioridad, df_minimos = cargar_datos(uploaded_file)
            df_stock, df_prioridad, df_minimos, prioridad_clientes, clientes_ordenados = preprocesar_datos(df_stock, df_prioridad, df_minimos)
            df_asignacion, df_minimos = asignar_stock(df_stock, df_minimos, prioridad_clientes, clientes_ordenados)
            df_minimos = calcular_resultados(df_asignacion, df_minimos)
            output = exportar_excel(df_asignacion, df_stock, df_prioridad, df_minimos)

            st.success("✅ Optimización completada.")

            st.subheader("📊 Total asignado por cliente")
            asignado_total = df_asignacion.sum().sort_values(ascending=False)
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            sns.barplot(x=asignado_total.index, y=asignado_total.values, ax=ax1)
            ax1.set_title("Total Asignado por Cliente")
            ax1.set_ylabel("Unidades Asignadas")
            ax1.set_xlabel("Cliente")
            ax1.tick_params(axis='x', rotation=45)
            st.pyplot(fig1)

            st.subheader("📈 Evolución mensual por cliente")
            df_plot = df_asignacion.reset_index().melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
            df_cliente_mes = df_plot.groupby(["MES", "Cliente"])["Asignado"].sum().reset_index()
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            sns.lineplot(data=df_cliente_mes, x="MES", y="Asignado", hue="Cliente", marker="o", ax=ax2)
            ax2.set_title("Evolución mensual de asignación")
            ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            st.pyplot(fig2)

            st.subheader("📦 Stock asignado vs restante por mes")
            df_stock_total = df_stock.reset_index().groupby("MES")[["Stock Disponible", "Stock Restante"]].sum()
            df_stock_total["Stock Asignado"] = df_stock_total["Stock Disponible"] - df_stock_total["Stock Restante"]
            df_melted = df_stock_total[["Stock Asignado", "Stock Restante"]].reset_index().melt(id_vars="MES", var_name="Tipo", value_name="Unidades")
            fig3, ax3 = plt.subplots(figsize=(8, 4))
            
sns.barplot(data=df_melted, x="MES", y="Unidades", hue="Tipo", ax=ax3)
ax3.set_title("Distribución de stock por mes")
ax3.set_ylabel("Unidades")
ax3.set_xlabel("Mes")
st.pyplot(fig3)

st.download_button(
    label="📥 Descargar archivo Excel",
    data=output.getvalue(),
    file_name="asignacion_resultados_PIAT_v1_5.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
