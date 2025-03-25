import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes")

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

# 📁 Subida del archivo
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# ℹ️ Ayuda al usuario
with st.expander("ℹ️ ¿Cómo interpretar el archivo descargado?"):
    st.markdown("""
    El archivo de resultados contiene dos hojas principales:

    ### 📄 Asignación Óptima
    Una tabla donde:
    - Las filas muestran cada producto (`Código`) por mes
    - Las columnas son los clientes
    - El valor indica cuántas unidades se asignaron a ese cliente para ese producto en ese mes

    **Ejemplo:**
    Si ves que `Cliente A` tiene 20 en la fila `(2, ZAP010)`, significa:
    > En el **mes 2**, el cliente A recibió **20 unidades** del producto ZAP010

    ### 📄 Stock Disponible
    Una tabla con el stock por producto y mes:
    - `Stock Disponible`: lo que se tenía originalmente
    - `Stock Restante`: lo que no se logró asignar ese mes
    - Si quedó stock en un mes, se acumula para el siguiente

    **Tip:** Puedes usar filtros en Excel para analizar por mes, cliente o producto.

    ---
    ¿Tienes dudas? Contacta a tu equipo de planificación o al responsable del modelo 🧠
    """)

# 🚀 Proceso si hay archivo
if uploaded_file is not None:
    try:
        # 1. Cargar datos
        df_stock = pd.read_excel(uploaded_file, sheet_name='Stock Disponible')
        df_prioridad = pd.read_excel(uploaded_file, sheet_name='Prioridad Clientes', index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name='Mínimos de Asignación', index_col=[0, 1, 2])

        # 2. Filtrar y preparar
        df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].set_index(['MES', 'Codigo']).sort_index()
        codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)).intersection(df_minimos.index.get_level_values(1))

        if not codigos_comunes:
            st.error("❌ No se encontraron códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'. Verifica los datos.")
        else:
            prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
            clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

            # 3. Inicializar stock restante
            df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']
            meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

            # 4. Arrastrar stock de un mes a otro
            for mes in meses_ordenados:
                if mes > 1:
                    stock_anterior = df_stock_filtrado.loc[(mes - 1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
                    df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'] += stock_anterior.reindex(df_stock_filtrado.loc[(mes, slice(None))].index, fill_value=0).values
            df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

            # 5. Asignación
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

            # 6. Crear archivo en memoria
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
                df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")
            output.seek(0)

            # 7. Mostrar resultado
            st.success("✅ Optimización completada. Puedes descargar el archivo o revisar un resumen aquí abajo.")
            st.subheader("⬇️ Descargar archivo con resultados")
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output,
                file_name="asignacion_resultados_completo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.subheader("🔍 Vista previa: Asignación Óptima")
            st.dataframe(df_asignacion.head(10))

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
