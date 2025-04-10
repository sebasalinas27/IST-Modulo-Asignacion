# --- app.py actualizado con lógica de mínimos pendientes acumulativos ---
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

# Configurar la página
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes")

# Instrucciones iniciales
st.markdown(
    """
    Sube tu archivo Excel con las siguientes hojas:
    - `Stock Disponible`
    - `Mínimos de Asignación`
    - `Prioridad Clientes`

    ---
    📅 ¿No tienes un archivo?  
    👉 [Descargar archivo de prueba](https://github.com/sebasalinas27/IST-Modulo-Asignacion/raw/main/Template_Pruebas_PIAT.xlsx)
    """
)

# Subida de archivo
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# Ayuda expandible
with st.expander("ℹ️ ¿Cómo interpretar el archivo descargado?"):
    st.markdown("""
    El archivo de resultados contiene dos hojas principales:

    ### 📄 Asignación Óptima
    - Filas: cada producto (`Código`) por mes
    - Columnas: los clientes
    - Valores: unidades asignadas a ese cliente

    ### 📄 Stock Disponible
    - `Stock Disponible`: lo que se tenía
    - `Stock Restante`: lo que no se asignó
    """)

with st.expander("❗ Tips para evitar errores"):
    st.markdown("""
    - Usa nombres exactos en las hojas
    - Elimina filtros, fórmulas y filas vacías
    - Solo formato `.xlsx`
    """)

# Inicializar dataframe vacío
df_asignacion = pd.DataFrame()

if uploaded_file:
    try:
        # Cargar hojas
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0,1,2])

        # Mostrar resumen
        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].copy()
            df_stock_filtrado = df_stock_filtrado.set_index(['MES', 'Codigo']).sort_index()

            # ESTA ES LA LÍNEA CORRECTAMENTE UBICADA
            codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
            if len(codigos_comunes) == 0:
                st.warning("⚠️ No hay códigos en común. Se procesará solo el stock, sin asignaciones.")
            else:
                st.info(f"🔄 Se encontraron {len(codigos_comunes)} códigos comunes para asignación.")

            df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']
            prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:,0], errors='coerce').fillna(0)
            clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
            meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

            df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)
            df_minimos["Pendiente"] = df_minimos["Minimo"]

            for mes in meses_ordenados:
                if mes > 1:
                    stock_ant = df_stock_filtrado.loc[(mes-1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock_filtrado.index:
                            df_stock_filtrado.loc[(mes, codigo), 'Stock Disponible'] += valor
                            df_stock_filtrado.loc[(mes, codigo), 'Stock Restante'] += valor

                df_stock_mes = df_stock_filtrado.loc[mes]

                for cliente in clientes_ordenados:
                    pendientes = df_minimos[df_minimos["Pendiente"] > 0]
                    pendientes_cliente = pendientes[pendientes.index.get_level_values(2) == cliente]

                    for idx, fila in pendientes_cliente.iterrows():
                        m_origen, codigo, cli = idx
                        if (mes, codigo) not in df_stock_mes.index:
                            continue

                        stock_disp = df_stock_mes.at[codigo, 'Stock Restante']
                        pendiente = fila["Pendiente"]

                        if pendiente > 0 and stock_disp > 0:
                            asignado = min(pendiente, stock_disp)
                            df_asignacion.at[(mes, codigo), cliente] += asignado
                            df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= asignado
                            df_minimos.at[idx, "Pendiente"] -= asignado

            # Guardar Excel virtual
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
                df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")
            output.seek(0)

            # Botón de descarga
            st.success("✅ Optimización completada.")
            st.download_button(
                label="📅 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_completo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.subheader("🔍 Vista previa: Asignación Óptima")
            st.dataframe(df_asignacion.head(10))

            # --- Reportes Visuales ---
            st.subheader("📊 Reportes Visuales")

            total_por_cliente = df_asignacion.sum(axis=0).sort_values(ascending=False)
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            sns.barplot(x=total_por_cliente.index, y=total_por_cliente.values, ax=ax1)
            ax1.set_title("Asignación Total por Cliente")
            ax1.set_xlabel("Cliente")
            ax1.set_ylabel("Unidades Asignadas")
            plt.xticks(rotation=45)
            st.pyplot(fig1)

            df_stock_mes = df_stock_filtrado.reset_index().groupby("MES")[["Stock Disponible", "Stock Restante"]].sum()
            df_stock_mes["Stock Asignado"] = df_stock_mes["Stock Disponible"] - df_stock_mes["Stock Restante"]
            df_melted = df_stock_mes[["Stock Asignado", "Stock Restante"]].reset_index().melt(id_vars="MES", var_name="Tipo", value_name="Unidades")

            fig2, ax2 = plt.subplots(figsize=(8, 4))
            sns.barplot(data=df_melted, x="MES", y="Unidades", hue="Tipo", ax=ax2)
            ax2.set_title("Stock Asignado vs Stock Restante por Mes")
            st.pyplot(fig2)

            st.subheader("📈 Evolución de Asignación por Cliente")
            df_asignacion_reset = df_asignacion.reset_index()
            df_linea = df_asignacion_reset.melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
            df_cliente_mes = df_linea.groupby(["MES", "Cliente"])["Asignado"].sum().reset_index()
            fig3, ax3 = plt.subplots(figsize=(10, 5))
            sns.lineplot(data=df_cliente_mes, x="MES", y="Asignado", hue="Cliente", marker="o", ax=ax3)
            ax3.set_title("Asignación Total por Cliente en el Tiempo")
            ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            st.pyplot(fig3)

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
