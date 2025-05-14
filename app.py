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

# --- 2. Carga del archivo ---
archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])
if archivo:
    xls = pd.ExcelFile(archivo)
    df_stock = pd.read_excel(xls, sheet_name="Stock Disponible")
    df_minimos = pd.read_excel(xls, sheet_name="Mínimos de Asignación")
    df_prioridad = pd.read_excel(xls, sheet_name="Prioridad Clientes")

    mes_actual = datetime.now().strftime("%Y-%m")

    # --- 3. Filtrado y preparación de datos ---
    codigos_comunes = set(df_stock["Codigo"]).intersection(set(df_minimos["Codigo"]))
    df_stock = df_stock[df_stock["Codigo"].isin(codigos_comunes)]
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

    for i, codigo in enumerate(codigos):
        fila_min = df_minimos[df_minimos["Codigo"] == codigo][clientes].values.flatten()
        stock_disp = df_stock[df_stock["Codigo"] == codigo]["Stock Disponible"].values[0]

        c.extend([prioridad_dict.get(cliente, 5) for cliente in clientes])
        A_row = [1 if j // m == i else 0 for j in range(n * m)]
        A_eq.append(A_row)
        b_eq.append(stock_disp)

        for j, cliente in enumerate(clientes):
            minimo = fila_min[j]
            bounds.append((minimo, None))

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

        df_recomendaciones = pd.DataFrame(recomendaciones)
        df_recomendaciones = df_recomendaciones.sort_values(by=["Codigo", "Mes", "Prioridad"])

        st.success("Asignación finalizada y exportada correctamente")
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
            df_recomendaciones.to_excel(writer, sheet_name="Propuesta Reasignación PUSH", index=False)
        st.download_button("📥 Descargar resultado", data=output.getvalue(), file_name="asignacion_resultados_PIAT_v1_4.xlsx")

    else:
        st.error("No se pudo encontrar una solución óptima al problema de asignación.")
