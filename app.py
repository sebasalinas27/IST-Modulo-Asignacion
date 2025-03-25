# --- app.py final con reportes visuales ---
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
    📥 ¿No tienes un archivo?  
    👉 [Descargar archivo de prueba](https://github.com/sebasalinas27/IST-Modulo-Asignacion/raw/main/Template_Pruebas_PIAT.xlsx)
    """
)

# Subir archivo
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# Sección de ayuda expandible
with st.expander("ℹ️ ¿Cómo interpretar el archivo descargado?"):
    st.markdown("""
    El archivo de resultados contiene dos hojas principales:

    ### 📄 Asignación Óptima
    - Las filas muestran cada producto (`Código`) por mes
    - Las columnas son los clientes
    - El valor indica cuántas unidades se asignaron a ese cliente para ese producto en ese mes

    **Ejemplo:**  
    Si ves que `Cliente A` tiene 20 en la fila `(2, ZAP010)`, significa:
    > En el **mes 2**, el cliente A recibió **20 unidades** del producto ZAP010

    ### 📄 Stock Disponible
    - `Stock Disponible`: lo que se tenía originalmente
    - `Stock Restante`: lo que no se logró asignar ese mes
    - El stock sobrante se acumula para el siguiente mes

    **Tip:** Puedes usar filtros en Excel para analizar por mes, cliente o producto.
    """)

# Tips para evitar errores
with st.expander("❗ Tips para evitar errores"):
    st.markdown("""
    - Asegúrate que los nombres de las hojas sean exactos
    - No uses filtros ni fórmulas en el archivo
    - El archivo debe estar en formato `.xlsx` (no `.xls` ni `.csv`)
    """)

# Inicializar asignación vacía por si ocurre error
df_asignacion = pd.DataFrame()

if uploaded_file is not None:
    try:
        # Leer hojas
        df_stock = pd.read_excel(uploaded_file, sheet_name='Stock Disponible')
        df_prioridad = pd.read_excel(uploaded_file, sheet_name='Prioridad Clientes', index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name='Mínimos de Asignación', index_col=[0, 1, 2])

        # Mostrar resumen antes de ejecutar
        st.subheader("📊 Resumen del archivo cargado")
        total_productos = df_stock['Codigo'].nunique()
        total_clientes = df_prioridad.shape[0]
        total_meses = df_stock['MES'].nunique()
        total_minimos = (df_minimos['Minimo'] > 0).sum()

        st.write(f"- **Productos**: {total_productos}")
        st.write(f"- **Clientes**: {total_clientes}")
        st.write(f"- **Meses**: {total_meses}")
        st.write(f"- **Celdas con mínimo asignado**: {total_minimos}")

        # Botón para ejecutar
        if st.button("🔁 Ejecutar Asignación"):
            df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].set_index(['MES', 'Codigo']).sort_index()
            codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)).intersection(df_minimos.index.get_level_values(1))

            if not codigos_comunes:
                st.error("❌ No se encontraron códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'. Verifica los datos.")
            else:
                prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
                clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
                df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']
                meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

                for mes in meses_ordenados:
                    if mes > 1:
                        stock_anterior = df_stock_filtrado.loc[(mes - 1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
                        df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'] = df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'].fillna(0) + stock_anterior.reindex(df_stock_filtrado.loc[(mes, slice(None))].index, fill_value=0).values
                    df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

                df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

                for mes in meses_ordenados:
                    df_stock_mes = df_stock_filtrado.loc[mes]
                    df_minimos_mes = df_minimos.loc[mes] if mes in df_minimos.index else pd.DataFrame()

                    for cliente in clientes_ordenados:
                        for codigo in df_stock_mes.index:
                            minimo_requerido = df_minimos_mes.loc[(codigo, cliente), 'Minimo'] if (codigo, cliente) in df_minimos_mes.index else 0
                            stock_disponible = df_stock_mes.at[codigo, 'Stock Restante']

                            if minimo_requerido > 0:
                                if stock_disponible >= minimo_requerido:
                                    df_asignacion.at[(mes, codigo), cliente] = minimo_requerido
                                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= minimo_requerido
                                else:
                                    df_asignacion.at[(mes, codigo), cliente] = stock_disponible
                                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] = 0

                # Descargar resultado
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                    df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
                    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                    df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")

                st.success("✅ Optimización completada. Puedes descargar el archivo o revisar un resumen aquí abajo.")

                st.download_button(
                    label="📥 Descargar archivo Excel",
                    data=output.getvalue(),
                    file_name="asignacion_resultados_completo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.subheader("🔍 Vista previa: Asignación Óptima")
                st.dataframe(df_asignacion.head(10))

                # --- Reportes Visuales ---
                st.subheader("📊 Reportes Visuales")

                # 1. Asignación total por cliente
                asignacion_total_cliente = df_asignacion.sum(axis=0).sort_values(ascending=False)

                fig1, ax1 = plt.subplots(figsize=(10, 4))
                sns.barplot(x=asignacion_total_cliente.index, y=asignacion_total_cliente.values, ax=ax1)
                ax1.set_title("Asignación Total por Cliente")
                ax1.set_xlabel("Cliente")
                ax1.set_ylabel("Unidades Asignadas")
                plt.xticks(rotation=45)
                st.pyplot(fig1)

                # 2. Stock asignado vs restante por mes
                df_stock_por_mes = df_stock_filtrado.reset_index().groupby("MES")[["Stock Disponible", "Stock Restante"]].sum()
                df_stock_por_mes["Stock Asignado"] = df_stock_por_mes["Stock Disponible"] - df_stock_por_mes["Stock Restante"]

                df_melted = df_stock_por_mes[["Stock Asignado", "Stock Restante"]].reset_index().melt(id_vars="MES", var_name="Tipo", value_name="Unidades")

                fig2, ax2 = plt.subplots(figsize=(8, 4))
                sns.barplot(data=df_melted, x="MES", y="Unidades", hue="Tipo", ax=ax2)
                ax2.set_title("Stock Asignado vs Stock Restante por Mes")
                ax2.set_xlabel("Mes")
                ax2.set_ylabel("Unidades")
                st.pyplot(fig2)

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
