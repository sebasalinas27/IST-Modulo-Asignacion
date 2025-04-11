# --- app.py FINAL ESTABLE con manejo robusto de índices ---
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

df_asignacion = pd.DataFrame()

if uploaded_file:
    try:
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0,1,2])
        df_minimos = df_minimos.groupby(level=[0, 1, 2], as_index=True).sum()
        df_minimos["Pendiente"] = df_minimos["Minimo"]

        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            try:
                df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].copy()
                df_stock_filtrado = df_stock_filtrado.set_index(['MES', 'Codigo']).sort_index()
                df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

                codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
                st.info(f"🔄 Se encontraron {len(codigos_comunes)} códigos comunes para asignación.")

                df_stock_filtrado = df_stock_filtrado[df_stock_filtrado.index.get_level_values(1).isin(codigos_comunes)]
                df_minimos = df_minimos[df_minimos.index.get_level_values(1).isin(codigos_comunes)]

                prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:,0], errors='coerce').fillna(0)
                clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
                meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

                df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

                for mes in meses_ordenados:
                    if mes > 1:
                        stock_ant = df_stock_filtrado.loc[(mes-1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
                        for codigo, valor in stock_ant.items():
                            if (mes, codigo) in df_stock_filtrado.index:
                                df_stock_filtrado.loc[(mes, codigo), 'Stock Disponible'] += valor
                                df_stock_filtrado.loc[(mes, codigo), 'Stock Restante'] += valor

                    df_stock_mes = df_stock_filtrado[df_stock_filtrado.index.get_level_values(0) == mes]

                    for cliente in clientes_ordenados:
                        pendientes_cliente = df_minimos.loc[
                            (df_minimos.index.get_level_values(0) <= mes) &
                            (df_minimos.index.get_level_values(2) == cliente)
                        ]
                        pendientes_cliente = pendientes_cliente[pendientes_cliente["Pendiente"] > 0]

                        for idx, fila in pendientes_cliente.iterrows():
                            m_origen, codigo, cli = idx
                            if (mes, codigo) not in df_stock_filtrado.index:
                                continue

                            stock_disp = df_stock_filtrado.loc[(mes, codigo), 'Stock Restante']
                            if isinstance(stock_disp, (pd.Series, np.ndarray)):
                                stock_disp = stock_disp.iloc[0] if len(stock_disp) > 0 else 0

                            idx_actual = (mes, codigo, cliente)
                            if idx_actual not in df_minimos.index:
                                st.warning(f"⚠️ idx no encontrado en df_minimos: {idx_actual}")
                                df_minimos = df_minimos.append(
                                    pd.DataFrame({"Minimo": [0], "Pendiente": [0]},
                                                 index=pd.MultiIndex.from_tuples([idx_actual], names=df_minimos.index.names))
                                )

                            pendiente = fila["Pendiente"]
                            if isinstance(pendiente, (pd.Series, np.ndarray)):
                                pendiente = pendiente.iloc[0] if len(pendiente) > 0 else 0

                            if pendiente > 0 and stock_disp > 0:
                                asignado = min(pendiente, stock_disp)
                                df_asignacion.at[(mes, codigo), cliente] += asignado
                                df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= asignado
                                df_minimos.loc[idx, "Pendiente"] = df_minimos.loc[idx, "Pendiente"] - asignado

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

                st.subheader("🔍 Vista previa: Asignación Óptima")
                st.dataframe(df_asignacion.head(10))

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

            except Exception as e:
                st.error(f"❌ Error al ejecutar la asignación: {type(e)} — {str(e)}")

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {str(e)}")
