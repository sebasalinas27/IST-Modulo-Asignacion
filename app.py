# --- PIAT v1.4: Asignación de Stock con códigos no asignados incluidos ---

import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
from scipy.optimize import linprog
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. Configuración inicial ---
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.4)")

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

# --- 2. Carga del archivo y vista previa + resumen ---
archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])
if archivo:
    st.subheader("📋 Vista previa de la carga")
    xls = pd.ExcelFile(archivo)
    df_stock = pd.read_excel(xls, sheet_name="Stock Disponible")
    df_minimos = pd.read_excel(xls, sheet_name="Mínimos de Asignación")
    df_prioridad = pd.read_excel(xls, sheet_name="Prioridad Clientes")

    st.write("**Hojas detectadas:**", xls.sheet_names)
    st.write("**Dimensiones del Stock Disponible:**", df_stock.shape)
    st.write("**Dimensiones de Mínimos de Asignación:**", df_minimos.shape)
    st.write("**Dimensiones de Prioridad Clientes:**", df_prioridad.shape)

    st.subheader("📊 Resumen del archivo cargado")
    st.write(f"- **Productos**: {df_stock['Codigo'].nunique()}")
    st.write(f"- **Clientes**: {df_prioridad.shape[0]}")
    st.write(f"- **Meses**: {df_stock['MES'].nunique() if 'MES' in df_stock.columns else 1}")
    if 'Minimo' in df_minimos.columns:
        st.write(f"- **Celdas con mínimo asignado**: {(df_minimos['Minimo'] > 0).sum()}")

    if st.button("🔁 Ejecutar Asignación"):
        mes_actual = datetime.now().strftime("%Y-%m")

        # --- 3. Filtrado, acumulación y preparación de datos ---
        
        codigos_comunes = set(df_stock["Codigo"]).intersection(set(df_minimos["Codigo"]))
        df_minimos = df_minimos[df_minimos["Codigo"].isin(codigos_comunes)]

        df_prioridad["Prioridad"] = pd.to_numeric(df_prioridad["Prioridad"], errors='coerce')
        df_prioridad = df_prioridad.dropna(subset=["Prioridad"])

        clientes = df_minimos.columns[1:]
        codigos = sorted(df_minimos["Codigo"].unique())

        n = len(codigos)
        m = len(clientes)

        c = []
        A_eq = []
        b_eq = []
        bounds = []

        prioridad_dict = df_prioridad.set_index("Cliente")["Prioridad"].to_dict()

        if 'MES' in df_stock.columns:
            df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()
            df_stock = df_stock.set_index(["MES", "Codigo"]).sort_index()
            df_stock["Stock Restante"] = df_stock["Stock Disponible"]
            meses = sorted(df_stock.index.get_level_values(0).unique())
            for mes in meses:
                if mes > min(meses):
                    stock_ant = df_stock.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock.index:
                            df_stock.loc[(mes, codigo), "Stock Disponible"] += valor
                            df_stock.loc[(mes, codigo), "Stock Restante"] += valor
            df_stock["Stock Restante"] = df_stock["Stock Disponible"]
            meses = sorted(df_stock.index.get_level_values(0).unique())
            for mes in meses:
                if mes > min(meses):
                    stock_ant = df_stock.loc[(mes-1, slice(None)), "Stock Restante"].groupby(level=1).sum()
                    for codigo, valor in stock_ant.items():
                        if (mes, codigo) in df_stock.index:
                            df_stock.loc[(mes, codigo), ["Stock Disponible", "Stock Restante"]] += valor

            

        for i, codigo in enumerate(codigos):
            fila_min = df_minimos[df_minimos["Codigo"] == codigo][clientes].values.flatten()

            if isinstance(df_stock.index, pd.MultiIndex):
                stock_codigo_df = df_stock.xs(codigo, level=1, drop_level=False)
            else:
                stock_codigo_df = df_stock[df_stock["Codigo"] == codigo]

            if stock_codigo_df.empty:
                st.warning(f"Código {codigo} no tiene stock disponible. Se omite del modelo.")
                continue

            stock_disp = stock_codigo_df["Stock Disponible"].sum()

            c.extend([prioridad_dict.get(cliente, 5) for cliente in clientes])
            A_row = [1 if j // m == i else 0 for j in range(n * m)]
            A_eq.append(A_row)
            b_eq.append(stock_disp)

            for j, cliente in enumerate(clientes):
                minimo = fila_min[j]
                bounds.append((minimo, None))

        if not (len(c) == len(bounds) == len(A_eq[0]) and len(A_eq) == len(b_eq)):
            st.error("❌ Error: Dimensiones inconsistentes en el modelo de optimización.")
            st.write(f"len(c): {len(c)}, len(bounds): {len(bounds)}, A_eq shape: {len(A_eq)}x{len(A_eq[0])}, len(b_eq): {len(b_eq)}")
            st.stop()

        resultado = linprog(c=c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if resultado.success:
            asignaciones = resultado.x.reshape((n, m))
            filas = []
            for i, codigo in enumerate(codigos):
                for j, cliente in enumerate(clientes):
                    filas.append({
                        "Codigo": codigo,
                        "Cliente": cliente,
                        "Mes": mes_actual,
                        "Asignado": round(asignaciones[i, j], 2)
                    })

            df_resultado_optimo = pd.DataFrame(filas)

            stock_total = df_stock.groupby("Codigo")["Stock Disponible"].sum()
            asignado_total = df_resultado_optimo.groupby("Codigo")["Asignado"].sum()
            diferencias = stock_total.subtract(asignado_total, fill_value=0)
            diferencias_restantes = diferencias[diferencias > 0].reset_index()

            df_no_asignado = diferencias_restantes.rename(columns={"Stock Disponible": "Asignado"})
            df_no_asignado["Cliente"] = "NO ASIGNADO"
            df_no_asignado["Mes"] = mes_actual
            df_no_asignado["Motivo"] = "Stock sin mínimos asignados"
            columnas_orden = ["Codigo", "Cliente", "Mes", "Asignado", "Motivo"]
            df_no_asignado = df_no_asignado[columnas_orden]

            df_resultado_optimo["Motivo"] = "Asignación óptima"
            df_resultado_final = pd.concat([df_resultado_optimo, df_no_asignado], ignore_index=True)

            st.success("✅ Asignación finalizada y exportada correctamente")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_resultado_final.to_excel(writer, sheet_name="Asignación óptima", index=False)
                df_pivot = df_resultado_final.pivot_table(
                    index=["Mes", "Codigo"],
                    columns="Cliente",
                    values="Asignado",
                    fill_value=0
                ).reset_index()
                df_pivot.to_excel(writer, sheet_name="Asignación Pivot", index=False)
            st.download_button("📥 Descargar resultado", data=output.getvalue(), file_name="asignacion_resultados_PIAT_v1_4.xlsx")

            # --- Proceso independiente: propuesta de reasignación PUSH ---
            st.subheader("📤 Generar hoja de propuesta PUSH (opcional)")
            if st.button("Generar propuesta de reasignación PUSH"):
                df_push = df_resultado_final[df_resultado_final["Cliente"] == "PUSH"]
                df_cumplidos = df_resultado_optimo.copy()
                df_cumplidos = df_cumplidos.merge(df_minimos.melt(id_vars="Codigo", var_name="Cliente", value_name="Minimo"),
                                                  on=["Codigo", "Cliente"], how="left")
                df_cumplidos = df_cumplidos[df_cumplidos["Asignado"] >= df_cumplidos["Minimo"]]
                df_cumplidos = df_cumplidos.merge(df_prioridad, on="Cliente", how="left")

                recomendaciones = []
                for _, fila in df_push.iterrows():
                    codigo, mes, push_qty = fila["Codigo"], fila["Mes"], fila["Asignado"]
                    clientes_candidatos = df_cumplidos[(df_cumplidos["Codigo"] == codigo) & (df_cumplidos["Mes"] == mes)]
                    for _, row in clientes_candidatos.iterrows():
                        recomendaciones.append({
                            "Codigo": codigo,
                            "Mes": mes,
                            "Cliente Propuesto": row["Cliente"],
                            "Asignado Actual": row["Asignado"],
                            "Minimo Requerido": row["Minimo"],
                            "Diferencia Potencial": push_qty,
                            "Prioridad": row["Prioridad"]
                        })

                df_recomendaciones = pd.DataFrame(recomendaciones).sort_values(by=["Codigo", "Mes", "Prioridad"])

                output_push = io.BytesIO()
                with pd.ExcelWriter(output_push, engine="xlsxwriter") as writer:
                    df_recomendaciones.to_excel(writer, sheet_name="Propuesta Reasignación PUSH", index=False)

                st.download_button(
                    label="📥 Descargar propuesta PUSH",
                    data=output_push.getvalue(),
                    file_name="propuesta_reasignacion_push.xlsx"
                )
                st.success("✅ Propuesta PUSH generada correctamente")
