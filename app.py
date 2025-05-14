# ✅ PIAT v1.3 - Versión con propuesta PUSH separada
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.3)")

st.markdown("""
### ✅ ¿Qué hace este módulo?

- Asigna productos considerando **mínimos requeridos por cliente y mes**
- Utiliza el **stock restante de meses anteriores**
- Prioriza clientes por nivel definido (1 es mayor prioridad)
- Aprovecha el stock no solicitado asignándolo a un cliente ficticio **PUSH**
- Exporta un archivo Excel con todas las vistas necesarias
""")

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

if uploaded_file:
    try:
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])

        df_minimos = df_minimos.groupby(level=[0, 1, 2]).sum().sort_index()
        df_minimos["Pendiente"] = df_minimos["Minimo"]

        prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(5)
        clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
        st.write(f"- **Meses**: {df_stock['MES'].nunique()}")
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

        if st.button("🔁 Ejecutar Asignación"):
            df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()
            df_stock = df_stock.set_index(["MES", "Codigo"]).sort_index()
            df_stock["Stock Restante"] = df_stock["Stock Disponible"]

            codigos_validos = set(df_stock.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
            df_stock = df_stock[df_stock.index.get_level_values(1).isin(codigos_validos)]
            df_minimos = df_minimos[df_minimos.index.get_level_values(1).isin(codigos_validos)]

            meses = sorted(df_stock.index.get_level_values(0).unique())
            df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados + ["PUSH"])
            minimos_agregados = set()

            index_minimos = df_minimos.index
            index_asignacion = df_asignacion.index

            for mes in meses:
                if mes > 1:
                    stock_ant = df_stock.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock.index:
                            df_stock.loc[(mes, codigo), ["Stock Disponible", "Stock Restante"]] += valor

                pendientes_mes = df_minimos[(df_minimos.index.get_level_values(0) <= mes)]
                pendientes_mes = pendientes_mes[pendientes_mes["Pendiente"] > 0]

                for (m_orig, codigo, cliente), fila in pendientes_mes.groupby(level=[0,1,2]):
                    if (mes, codigo) not in df_stock.index:
                        continue

                    idx_actual = (mes, codigo, cliente)
                    if idx_actual not in index_minimos and idx_actual not in minimos_agregados:
                        df_minimos.loc[idx_actual, ["Minimo", "Pendiente"]] = 0
                        minimos_agregados.add(idx_actual)

                    stock_disp = df_stock.at[(mes, codigo), "Stock Restante"]
                    pendiente = df_minimos.at[(m_orig, codigo, cliente), "Pendiente"]

                    if pendiente > 0 and stock_disp > 0:
                        asignado = min(pendiente, stock_disp)
                        if (mes, codigo) not in index_asignacion:
                            df_asignacion.loc[(mes, codigo), :] = 0
                            index_asignacion = df_asignacion.index
                        df_asignacion.at[(mes, codigo), cliente] += asignado
                        df_stock.at[(mes, codigo), "Stock Restante"] -= asignado
                        df_minimos.at[(m_orig, codigo, cliente), "Pendiente"] -= asignado

                sobrantes = df_stock.loc[mes]["Stock Restante"]
                sobrantes = sobrantes[sobrantes > 0]
                for codigo, restante in sobrantes.items():
                    if (mes, codigo) not in index_asignacion:
                        df_asignacion.loc[(mes, codigo), :] = 0
                        index_asignacion = df_asignacion.index
                    df_asignacion.at[(mes, codigo), "PUSH"] += restante
                    df_stock.at[(mes, codigo), "Stock Restante"] = 0

            df_minimos["Asignado"] = df_minimos.index.map(
                lambda x: df_asignacion.at[(x[0], x[1]), x[2]] if (x[0], x[1]) in df_asignacion.index else 0
            )
            df_minimos["Cumple"] = df_minimos["Asignado"] >= df_minimos["Minimo"]
            df_minimos["Pendiente Final"] = df_minimos["Minimo"] - df_minimos["Asignado"]

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
                df_stock.reset_index().to_excel(writer, sheet_name="Stock Disponible", index=False)
                df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
                df_minimos.reset_index().to_excel(writer, sheet_name="Mínimos de Asignación", index=False)
            output.seek(0)

            st.success("✅ Optimización completada.")
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_PIAT_v1_3.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.subheader("📤 Generar hoja de propuesta PUSH (opcional)")

            if st.button("Generar propuesta de reasignación PUSH"):
                df_push = df_asignacion.reset_index().melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
                df_push = df_push[df_push["Cliente"] == "PUSH"]

                df_asignado = df_asignacion.reset_index().melt(id_vars=["MES", "Codigo"], var_name="Cliente", value_name="Asignado")
                df_asignado = df_asignado[df_asignado["Cliente"] != "PUSH"]

                df_minimos_exp = df_minimos.reset_index()[["MES", "Codigo", "Cliente", "Minimo"]]
                df_asignado = df_asignado.merge(df_minimos_exp, on=["MES", "Codigo", "Cliente"], how="left")
                df_asignado = df_asignado[df_asignado["Asignado"] >= df_asignado["Minimo"]]

                df_prioridad_reset = df_prioridad.reset_index().rename(columns={df_prioridad.columns[0]: "Cliente"})
                df_asignado = df_asignado.merge(df_prioridad_reset, on="Cliente", how="left")

                recomendaciones = []
                for _, push_row in df_push.iterrows():
                    codigo = push_row["Codigo"]
                    mes = push_row["MES"]
                    cantidad_push = push_row["Asignado"]
                    candidatos = df_asignado[(df_asignado["Codigo"] == codigo) & (df_asignado["MES"] == mes)]

                    for _, row in candidatos.iterrows():
                        recomendaciones.append({
                            "Codigo": codigo,
                            "Mes": mes,
                            "Cliente Propuesto": row["Cliente"],
                            "Asignado Actual": row["Asignado"],
                            "Minimo Requerido": row["Minimo"],
                            "Diferencia Potencial": cantidad_push,
                            "Prioridad": row["Prioridad"]
                        })

                df_recomendaciones = pd.DataFrame(recomendaciones)

                if not df_recomendaciones.empty:
                    df_recomendaciones = df_recomendaciones.sort_values(by=["Codigo", "Mes", "Prioridad"])
                    output_push = io.BytesIO()
                    with pd.ExcelWriter(output_push, engine="xlsxwriter") as writer:
                        df_recomendaciones.to_excel(writer, sheet_name="Propuesta Reasignación PUSH", index=False)
                    st.session_state["push_result"] = output_push.getvalue()
                    st.session_state["push_ready"] = True
                    st.success("✅ Propuesta PUSH generada correctamente")
                else:
                    st.session_state["push_ready"] = False
                    st.info("No hay sugerencias posibles a partir de los datos cargados.")

            if st.session_state.get("push_ready", False):
                st.download_button(
                    label="📥 Descargar propuesta PUSH",
                    data=st.session_state["push_result"],
                    file_name="propuesta_reasignacion_push.xlsx"
                )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
