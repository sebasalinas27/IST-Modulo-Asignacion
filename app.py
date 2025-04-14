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

df_asignacion = pd.DataFrame()

if uploaded_file:
    try:
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0,1,2])

        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].copy()
            df_stock_filtrado = df_stock_filtrado.set_index(['MES', 'Codigo']).sort_index()
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

            for mes in meses_ordenados:
                if mes > 1:
                    stock_ant = df_stock_filtrado.loc[(mes-1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock_filtrado.index:
                            df_stock_filtrado.loc[(mes, codigo), 'Stock Disponible'] += valor
                            df_stock_filtrado.loc[(mes, codigo), 'Stock Restante'] += valor

                df_stock_mes = df_stock_filtrado.loc[mes]
                df_minimos_mes = df_minimos.loc[mes] if mes in df_minimos.index else pd.DataFrame()

                for cliente in clientes_ordenados:
                    for codigo in df_stock_mes.index:
                        if (codigo, cliente) in df_minimos_mes.index:
                            minimo = df_minimos_mes.loc[(codigo, cliente), 'Minimo']
                        else:
                            minimo = 0

                        if minimo > 0:
                            stock_disp = df_stock_mes.at[codigo, 'Stock Restante']
                            asignado = min(minimo, stock_disp) if stock_disp >= minimo else stock_disp
                            df_asignacion.at[(mes, codigo), cliente] = asignado
                            df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= asignado
