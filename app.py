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

        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            codigos_comunes = set(df_stock["Codigo"].unique()) & set(df_minimos_reset["Codigo"].unique())
            df_stock_filtrado = df_stock[df_stock["Codigo"].isin(codigos_comunes)].copy()
            df_minimos = df_minimos[df_minimos.index.get_level_values("Codigo").isin(codigos_comunes)]
            prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
            clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

            df_stock_filtrado = df_stock_filtrado.set_index(["MES", "Codigo"]).sort_index()
            df_stock_filtrado["Stock Restante"] = df_stock_filtrado["Stock Disponible"]

            df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel("Cliente").unique(), columns=clientes_ordenados)

            for (mes, codigo, cliente), fila in df_minimos.iterrows():
                if (mes, codigo) not in df_stock_filtrado.index:
                    continue
                stock_disp = df_stock_filtrado.loc[(mes, codigo), "Stock Restante"]
                pendiente = fila["Pendiente"]
                if stock_disp > 0 and pendiente > 0:
                    asignado = min(pendiente, stock_disp)
                    df_asignacion.at[(mes, codigo), cliente] += asignado
                    df_stock_filtrado.loc[(mes, codigo), "Stock Restante"] -= asignado
                    df_minimos.loc[(mes, codigo, cliente), "Pendiente"] -= asignado

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

            # GRAFICOS EN STREAMLIT
            st.subheader("📈 Cumplimiento por Cliente")
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            sns.barplot(
                data=resumen_clientes.reset_index(),
                x="Cliente", y="% Cumplido", palette="Blues_d", ax=ax1
            )
            ax1.set_title("Porcentaje de Cumplimiento por Cliente")
            ax1.set_ylim(0, 110)
            ax1.set_ylabel("% Cumplido")
            ax1.set_xlabel("Cliente")
            plt.xticks(rotation=45)
            st.pyplot(fig1)

            st.subheader("🏆 Top 10 Clientes por Asignación Total")
            top_clientes = resumen_clientes.sort_values("Total_Asignado", ascending=False).head(10)
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            sns.barplot(
                data=top_clientes.reset_index(),
                x="Cliente", y="Total_Asignado", palette="Greens_d", ax=ax2
            )
            ax2.set_title("Top 10 Clientes - Total Asignado")
            ax2.set_ylabel("Unidades Asignadas")
            ax2.set_xlabel("Cliente")
            plt.xticks(rotation=45)
            st.pyplot(fig2)

            st.subheader("📦 Stock Restante por Mes")
            stock_restante_mes = df_stock_filtrado.reset_index().groupby("MES")["Stock Restante"].sum().reset_index()
            fig3, ax3 = plt.subplots(figsize=(8, 4))
            sns.barplot(data=stock_restante_mes, x="MES", y="Stock Restante", palette="Reds_d", ax=ax3)
            ax3.set_title("Distribución de Stock Restante por Mes")
            ax3.set_ylabel("Unidades sin Asignar")
            ax3.set_xlabel("Mes")
            st.pyplot(fig3)

            st.subheader("📅 Flujo de Asignación por Mes")
            flujo_mes = df_asignacion_reset.groupby("MES")["Asignado"].sum().reset_index()
            fig4, ax4 = plt.subplots(figsize=(8, 4))
            sns.lineplot(data=flujo_mes, x="MES", y="Asignado", marker="o", ax=ax4)
            ax4.set_title("Flujo de Asignación Total por Mes")
            ax4.set_ylabel("Unidades Asignadas")
            ax4.set_xlabel("Mes")
            ax4.grid(True)
            st.pyplot(fig4)

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

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
