# -*- coding: utf-8 -*-
"""
PIAT v1.3 - Sistema de Asignación de Stock con:
- Prioridad de clientes
- Flujo continuo entre meses
- Asignación residual a PUSH
- Validación completa de stock
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración básica
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.3)")

# Sección de instrucciones
with st.expander("📌 Instrucciones", expanded=True):
    st.markdown("""
    ### Cómo usar esta herramienta:
    1. Sube tu archivo Excel con las hojas requeridas
    2. Revisa el resumen de datos cargados
    3. Ejecuta la asignación automática
    4. Descarga los resultados completos
    
    **Hojas requeridas:**
    - `Stock Disponible` - Stock disponible por mes y código
    - `Mínimos de Asignación` - Requerimientos por cliente
    - `Prioridad Clientes` - Niveles de prioridad (1 = mayor prioridad)
    """)

# Carga de archivo
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# Procesamiento principal
if uploaded_file:
    try:
        # Carga y preparación de datos
        with st.spinner("Cargando y validando datos..."):
            # Leer hojas de Excel
            df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
            df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
            df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])
            
            # Procesamiento inicial de mínimos
            df_minimos = df_minimos.groupby(level=[0, 1, 2]).sum().sort_index()
            df_minimos["Pendiente"] = df_minimos["Minimo"]
            
            # Prioridad de clientes
            prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(5)
            clientes_ordenados = prioridad_clientes.sort_values().index.tolist() + ["PUSH"]

        # Mostrar resumen de datos
        st.subheader("📊 Resumen de Datos Cargados")
        col1, col2, col3 = st.columns(3)
        col1.metric("Productos Únicos", df_stock['Codigo'].nunique())
        col2.metric("Clientes", df_prioridad.shape[0])
        col3.metric("Meses", df_stock['MES'].nunique())
        
        if st.button("🚀 Ejecutar Asignación Automática", type="primary"):
            with st.spinner("Optimizando asignación..."):
                # Preparación de datos
                df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()
                df_stock = df_stock.set_index(["MES", "Codigo"]).sort_index()
                df_stock["Stock Restante"] = df_stock["Stock Disponible"]
                
                # Conservar TODOS los códigos de Stock Disponible
                codigos_stock = set(df_stock.index.get_level_values(1))
                codigos_minimos = set(df_minimos.index.get_level_values(1))
                
                # Crear mínimos cero para códigos no definidos
                for codigo in codigos_stock - codigos_minimos:
                    for mes in df_stock.xs(codigo, level=1).index.unique():
                        for cliente in clientes_ordenados[:-1]:  # Excluye PUSH
                            df_minimos.loc[(mes, codigo, cliente)] = [0, 0, 0]  # Mínimo cero
                
                # Procesar todos los meses disponibles
                meses = sorted(df_stock.index.get_level_values(0).unique())
                df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), 
                                          columns=clientes_ordenados)
                minimos_agregados = set()
                
                # Barra de progreso
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Proceso de asignación por mes
                for i, mes in enumerate(meses):
                    status_text.text(f"Procesando mes {mes}...")
                    progress_bar.progress((i + 1) / len(meses))
                    
                    # Arrastre de stock del mes anterior
                    if mes > 1:
                        stock_ant = df_stock.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
                        for codigo, valor in stock_ant.items():
                            if (mes, codigo) in df_stock.index:
                                df_stock.loc[(mes, codigo), ["Stock Disponible", "Stock Restante"]] += valor
                    
                    # Asignación por prioridad
                    for cliente in clientes_ordenados[:-1]:  # Excluye PUSH
                        pendientes = df_minimos[
                            (df_minimos.index.get_level_values(0) <= mes) & 
                            (df_minimos.index.get_level_values(2) == cliente) & 
                            (df_minimos["Pendiente"] > 0)
                        ]
                        
                        for idx, fila in pendientes.iterrows():
                            m_orig, codigo, cli = idx
                            if (mes, codigo) not in df_stock.index:
                                continue
                            
                            # Lógica de asignación
                            stock_disp = df_stock.loc[(mes, codigo), "Stock Restante"]
                            pendiente = fila["Pendiente"]
                            
                            if pendiente > 0 and stock_disp > 0:
                                asignado = min(pendiente, stock_disp)
                                df_asignacion.at[(mes, codigo), cliente] += asignado
                                df_stock.loc[(mes, codigo), "Stock Restante"] -= asignado
                                df_minimos.loc[idx, "Pendiente"] -= asignado
                    
                    # Asignación de sobrantes a PUSH
                    for (mes_c, codigo), fila_stock in df_stock.loc[mes].iterrows():
                        restante = fila_stock["Stock Restante"]
                        if restante > 0:
                            df_asignacion.at[(mes, codigo), "PUSH"] += restante
                            df_stock.loc[(mes, codigo), "Stock Restante"] = 0
                
                # Generación de reportes
                with st.spinner("Generando reportes..."):
                    df_minimos["Asignado"] = df_minimos.index.map(
                        lambda x: df_asignacion.at[(x[0], x[1]), x[2]] if (x[0], x[1]) in df_asignacion.index else 0
                    )
                    df_minimos["Cumple"] = df_minimos["Asignado"] >= df_minimos["Minimo"]
                    df_minimos["Pendiente Final"] = df_minimos["Minimo"] - df_minimos["Asignado"]
                    
                    resumen = df_minimos[df_minimos["Minimo"] > 0].groupby("Cliente").agg(
                        Total_Minimo=("Minimo", "sum"),
                        Total_Asignado=("Asignado", "sum")
                    )
                    resumen["% Cumplido"] = (resumen["Total_Asignado"] / resumen["Total_Minimo"] * 100).round(2)
                    
                    # Validación final
                    unidades_iniciales = df_stock["Stock Disponible"].sum()
                    unidades_asignadas = df_asignacion.sum().sum()
                    
                    # Resultados en pestañas
                    tab1, tab2, tab3 = st.tabs(["Resumen", "Gráficos", "Validación"])
                    
                    with tab1:
                        st.dataframe(resumen.style.format({
                            "Total_Minimo": "{:,.0f}",
                            "Total_Asignado": "{:,.0f}",
                            "% Cumplido": "{:.2f}%"
                        }))
                    
                    with tab2:
                        fig, ax = plt.subplots(1, 2, figsize=(12, 4))
                        
                        # Gráfico 1: Cumplimiento por cliente
                        resumen.sort_values("% Cumplido", ascending=False)["% Cumplido"].plot(
                            kind="bar", ax=ax[0], title="% de Cumplimiento por Cliente"
                        )
                        ax[0].axhline(100, color="red", linestyle="--")
                        
                        # Gráfico 2: Distribución de asignación
                        df_asignacion.sum().sort_values(ascending=False).plot(
                            kind="pie", ax=ax[1], title="Distribución Total de Asignación"
                        )
                        st.pyplot(fig)
                    
                    with tab3:
                        st.subheader("🧮 Validación Completa de Stock")
                        col1, col2 = st.columns(2)
                        col1.metric("Stock Inicial Total", unidades_iniciales)
                        col2.metric("Stock Asignado Total", unidades_asignadas)
                        
                        st.write("""
                        ### Balance Detallado:
                        - **Asignado a clientes prioritarios:** {:,}
                        - **Asignado a PUSH:** {:,}
                        - **Diferencia:** {:,}
                        """.format(
                            int(unidades_asignadas - df_asignacion["PUSH"].sum()),
                            int(df_asignacion["PUSH"].sum()),
                            int(unidades_iniciales - unidades_asignadas)
                        ))
                        
                        if unidades_iniciales == unidades_asignadas:
                            st.success("✔️ 100% del stock fue asignado correctamente")
                        else:
                            st.error("⚠️ Hay discrepancia en el balance de stock")
                
                # Generar archivo Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                    df_stock.reset_index().to_excel(writer, sheet_name="Stock Disponible", index=False)
                    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                    df_minimos.reset_index().to_excel(writer, sheet_name="Mínimos de Asignación", index=False)
                    resumen.reset_index().to_excel(writer, sheet_name="Resumen Clientes", index=False)
                output.seek(0)
                
                st.success("✅ Optimización completada exitosamente!")
                st.download_button(
                    label="📥 Descargar Resultados Completos",
                    data=output.getvalue(),
                    file_name="Resultados_Asignacion_PIAT.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"❌ Error en el procesamiento: {str(e)}")
        st.info("ℹ️ Verifica que el archivo tenga el formato correcto y todas las hojas requeridas")
