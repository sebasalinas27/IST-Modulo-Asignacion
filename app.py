# ✅ PIAT v1.5 - Con prioridad respetada y flujo en vez de PUSH
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.5 Prioridad Fix + Flujo continuo)")

st.markdown("""
### ✅ ¿Qué hace este módulo?

- Asigna productos considerando **mínimos requeridos por cliente y mes**
- Utiliza el **stock restante como flujo acumulado entre meses**
- Prioriza clientes por nivel definido (1 es mayor prioridad)
- El stock sobrante **se arrastra como flujo**, no se manda a `PUSH`
- Exporta un archivo Excel con todas las vistas necesarias
""")

# ... (código previo igual hasta antes del loop de meses)

            stock_flujo = {}  # Flujo acumulado de stock por código

            for mes in meses:
                for codigo in df_stock.index.get_level_values(1).unique():
                    if (mes, codigo) in df_stock.index:
                        disponible = df_stock.at[(mes, codigo), "Stock Restante"]
                        stock_flujo[codigo] = stock_flujo.get(codigo, 0) + disponible

                pendientes_mes = df_minimos[(df_minimos.index.get_level_values(0) == mes)]
                pendientes_mes = pendientes_mes[pendientes_mes["Pendiente"] > 0]
                pendientes_mes = pendientes_mes.reset_index()
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

            # Calcular asignado final por cliente
            df_minimos["Asignado"] = df_minimos.index.map(
                lambda x: df_asignacion.at[(x[0], x[1]), x[2]] if (x[0], x[1]) in df_asignacion.index else 0
            )
            df_minimos["Cumple"] = df_minimos["Asignado"] >= df_minimos["Minimo"]
            df_minimos["Pendiente Final"] = df_minimos["Minimo"] - df_minimos["Asignado"]

            # Eliminar columna PUSH si existe
            if "PUSH" in df_asignacion.columns:
                df_asignacion = df_asignacion.drop(columns=["PUSH"])

            # Continuación del código de exportación y visualización

            # 🧪 Verificación visual por código desde Streamlit
            st.subheader("🔍 Ver asignación por código específico")
            codigo_input = st.text_input("Ingresa un código exacto para revisar su asignación", value="713574 01")

            if codigo_input:
                df_codigo_vista = df_asignacion[df_asignacion.index.get_level_values(1) == codigo_input]
                if not df_codigo_vista.empty:
                    st.write(f"Asignación detallada para el código: `{codigo_input}`")
                    st.dataframe(df_codigo_vista)
                else:
                    st.warning("⚠️ No se encontró asignación para ese código.")
