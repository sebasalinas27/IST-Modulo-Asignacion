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
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos_raw = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")

        # Validar y preparar df_minimos
        df_minimos_raw = df_minimos_raw.dropna(subset=["MES", "Codigo", "Cliente"])
        df_minimos_raw["MES"] = df_minimos_raw["MES"].astype(int)

        # Agrupar mínimos y crear columna Pendiente
        df_minimos = df_minimos_raw.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"].sum().to_frame()
        df_minimos["Pendiente"] = df_minimos["Minimo"]

        # Reiniciar índice para consolidación de duplicados (si arrastró mínimo varias veces)
        df_minimos_reset = df_minimos.reset_index()

        # Verificar duplicados (MES, Código, Cliente)
        duplicados = df_minimos_reset.duplicated(subset=["MES", "Codigo", "Cliente"], keep=False)
        if duplicados.any():
            # Consolidar duplicados sumando mínimo y pendiente
            df_minimos_reset = df_minimos_reset.groupby(["MES", "Codigo", "Cliente"], as_index=False).agg({
                "Minimo": "sum",
                "Pendiente": "sum"
            })

        # Volver a MultiIndex ordenado
        df_minimos = df_minimos_reset.set_index(["MES", "Codigo", "Cliente"]).sort_index()

        if st.button("🔁 Ejecutar Asignación"):
            codigos_comunes = set(df_stock["Codigo"]) & set(df_minimos_reset["Codigo"])
            df_stock = df_stock[df_stock["Codigo"].isin(codigos_comunes)]
            df_minimos = df_minimos[df_minimos.index.get_level_values("Codigo").isin(codigos_comunes)]

            clientes = df_prioridad.index.tolist()
            df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes)

            for (mes, codigo, cliente), fila in df_minimos.iterrows():
                pendiente = fila["Pendiente"]
                stock_disp = df_stock.loc[(df_stock["MES"] == mes) & (df_stock["Codigo"] == codigo), "Stock Disponible"].sum()

                asignado = min(pendiente, stock_disp)
                if asignado > 0:
                    if (mes, codigo) not in df_asignacion.index:
                        df_asignacion.loc[(mes, codigo)] = [0] * len(df_asignacion.columns)
                    df_asignacion.at[(mes, codigo), cliente] += asignado

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

            # Exportar
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock.to_excel(writer, sheet_name="Stock Disponible", index=False)
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

            # Gráficos
            st.subheader("📊 Asignación Total por Cliente")
            total_por_cliente = df_asignacion.sum().sort_values(ascending=False)
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            sns.barplot(x=total_por_cliente.index, y=total_por_cliente.values, ax=ax1)
            ax1.set_ylabel("Unidades Asignadas")
            st.pyplot(fig1)

            st.subheader("📊 Flujo Mensual de Stock")
            df_stock_mes = df_stock.groupby("MES")[["Stock Disponible"]].sum()
            df_stock_mes["Stock Asignado"] = df_asignacion_reset.groupby("MES")["Asignado"].sum()
            df_stock_mes["Stock Restante"] = df_stock_mes["Stock Disponible"] - df_stock_mes["Stock Asignado"]
            df_melted = df_stock_mes.reset_index().melt(id_vars="MES", var_name="Tipo", value_name="Unidades")
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            sns.barplot(data=df_melted, x="MES", y="Unidades", hue="Tipo", ax=ax2)
            st.pyplot(fig2)

            st.subheader("📈 Evolución de Asignación por Cliente")
            df_cliente_mes = df_asignacion_reset.groupby(["MES", "Cliente"])["Asignado"].sum().reset_index()
            fig3, ax3 = plt.subplots(figsize=(10, 5))
            sns.lineplot(data=df_cliente_mes, x="MES", y="Asignado", hue="Cliente", marker="o", ax=ax3)
            ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            st.pyplot(fig3)

    except Exception as e:
        st.error(f"❌ Error al procesar la asignación: {type(e)} — {e}")
