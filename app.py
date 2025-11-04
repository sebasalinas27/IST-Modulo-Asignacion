# =========================================================
# PIAT v1.3.3 - Mínimos en MES=1, stock mes a mes, prioridad estricta
# Reglas:
# - Los mínimos existen solo en MES=1 y generan "Pendiente".
# - Cada mes, el stock que llega se asigna por código en fila de prioridad (1->2->3...).
# - Si sobra stock del mes (y no hay pendientes), va a PUSH del mismo mes.
# - NO se traslada stock entre meses.
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns

# =========================
# 1) Cabecera de la App
# =========================
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock (v1.3.3 — Mínimos M1, Stock por Mes, Prioridad)")

st.markdown("""
**Lógica v1.3.3**  
- Los **mínimos** se informan solo en **MES = 1** (nacen los pendientes).  
- El **stock** llega **mes a mes**; en cada mes se asigna **por código** a los clientes en **orden de prioridad**.  
- Si **sobra stock** del mes y **no hay pendientes**, va a **PUSH** (de ese mes).  
- **No se arrastra stock** al mes siguiente.
""")

st.markdown("""
Sube tu archivo Excel (mismo template de siempre):
- `Stock Disponible` → columnas: `MES`, `Codigo`, `Stock Disponible`
- `Mínimos de Asignación` → índice: `MES`, `Codigo`, `Cliente`; columna `Minimo` (**usa MES=1**)
- `Prioridad Clientes` → índice: `Cliente`; valor: prioridad (1 = mayor)
""")

uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# =========================
# 2) Helpers
# =========================
def norm_cliente(x):
    return x.strip() if isinstance(x, str) else x

# =========================
# 3) Proceso principal
# =========================
if uploaded_file:
    try:
        # -------------------------
        # 3.1 Carga de hojas
        # -------------------------
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prior = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_min   = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])

        # -------------------------
        # 3.2 Limpieza mínima
        # -------------------------
        df_stock.columns = [c.strip() for c in df_stock.columns]
        df_stock["Codigo"] = df_stock["Codigo"].astype(str).str.strip()
        df_stock["MES"] = pd.to_numeric(df_stock["MES"], errors="coerce").fillna(1).astype(int)
        df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()

        prioridad_series = pd.to_numeric(df_prior.iloc[:, 0], errors="coerce").fillna(5)
        prioridad_series.index = prioridad_series.index.map(norm_cliente)
        clientes_por_prioridad = prioridad_series.sort_values().index.tolist()

        # -------------------------
        # 3.3 Mínimos → solo MES=1 (consolidar si vienen otros)
        # -------------------------
        df_min = df_min.reset_index()
        df_min.columns = ["MES", "Codigo", "Cliente", "Minimo"]
        df_min["MES"] = 1
        df_min["Codigo"] = df_min["Codigo"].astype(str).str.strip()
        df_min["Cliente"] = df_min["Cliente"].map(norm_cliente)

        if "Minimo" not in df_min.columns:
            raise ValueError("La hoja 'Mínimos de Asignación' debe incluir la columna 'Minimo'.")

        df_min = (
            df_min.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"]
                 .sum()
                 .to_frame()
        )

        # -------------------------
        # 3.4 Intersección de códigos válidos
        # -------------------------
        cod_min = set(df_min.index.get_level_values(1))
        cod_stk = set(df_stock["Codigo"])
        cod_validos = sorted(cod_min & cod_stk)

        # -------------------------
        # 3.5 Resumen de entrada
        # -------------------------
        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos en stock**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes con prioridad**: {df_prior.shape[0]}")
        st.write(f"- **Celdas de mínimos (>0)**: {(df_min['Minimo'] > 0).sum()}")
        st.info("Esta versión **usa solo MES=1** para mínimos y **asigna stock por mes** en **orden de prioridad**. Sobrantes del mes → PUSH.")

        # -------------------------
        # 3.6 Ejecutar
        # -------------------------
        if st.button("🔁 Ejecutar Asignación (v1.3.3)"):
            # =========================
            # 4) Estructuras de trabajo
            # =========================

            # 4.1 Pendientes por (Codigo, Cliente): nacen en MES=1 a partir de 'Minimo'
            df_min_pos = df_min[df_min["Minimo"] > 0].copy()
            df_min_pos = df_min_pos[df_min_pos.index.get_level_values(1).isin(cod_validos)]

            # *** Importante: usar .items() para obtener (índice, valor) ***
            pendientes = {}
            for (mes, cod, cli), minimo in df_min_pos["Minimo"].items():
                pendientes[(cod, cli)] = int(minimo)

            # 4.2 Columnas de salida: clientes por prioridad presentes en los mínimos + PUSH
            meses = sorted(df_stock["MES"].unique())
            clientes_en_min = sorted(
                {cli for (_, _, cli) in df_min_pos.index},
                key=lambda x: prioridad_series.get(x, 999)
            )
            columnas_asig = (
                [c for c in clientes_por_prioridad if c in clientes_en_min] +
                [c for c in clientes_en_min if c not in clientes_por_prioridad] +
                ["PUSH"]
            )

            # 4.3 DataFrame de asignación con MultiIndex vacío (FIX del indexer)
            idx_empty = pd.MultiIndex.from_arrays([[], []], names=["MES", "Codigo"])
            df_asig = pd.DataFrame(columns=columnas_asig, index=idx_empty, dtype=float)

            # =========================
            # 5) Asignación mes a mes (prioridad estricta)
            # =========================
            for mes in meses:
                # Stock disponible de este mes por código
                stock_mes = (
                    df_stock[df_stock["MES"] == mes]
                    .groupby("Codigo")["Stock Disponible"]
                    .sum()
                )

                for codigo, stock_disp in stock_mes.items():
                    # Fila de salida inicial en 0 para este (MES, Codigo)
                    fila = pd.Series(0, index=columnas_asig, dtype=float)

                    if codigo not in cod_validos:
                        # No tiene mínimos → todo a PUSH del mes
                        fila["PUSH"] = float(stock_disp)
                        # Escribir SIEMPRE por columnas explícitas (evita crear columnas con el código)
                        df_asig.loc[(mes, codigo), columnas_asig] = fila.values
                        continue

                    # Recorremos clientes en orden de prioridad
                    for cliente in columnas_asig:
                        if cliente == "PUSH":
                            continue
                        pend = int(pendientes.get((codigo, cliente), 0))
                        if pend <= 0:
                            continue
                        if stock_disp <= 0:
                            break

                        asign = min(pend, int(stock_disp))
                        fila[cliente] += asign
                        pendientes[(codigo, cliente)] = pend - asign
                        stock_disp -= asign

                    # Si queda stock y ya no hay pendientes de nadie para ese código → PUSH del mes
                    if stock_disp > 0:
                        queda_pend = any(pendientes.get((codigo, c), 0) > 0 for c in columnas_asig if c != "PUSH")
                        if not queda_pend:
                            fila["PUSH"] = float(stock_disp)

                    # Escribir por columnas explícitas (clave para no deformar df_asig)
                    df_asig.loc[(mes, codigo), columnas_asig] = fila.values

            # Blindaje final: mismas columnas y sin NaN
            df_asig = df_asig.reindex(columns=columnas_asig).fillna(0)

            # =========================
            # 6) Métricas y salidas
            # =========================
            # 6.1 Asignado total por (Codigo, Cliente) = sumar en todos los meses
            df_asig_idx = df_asig.copy()  # ya tiene MultiIndex ["MES","Codigo"]
            df_asig_long = df_asig_idx.drop(columns=["PUSH"]).stack().reset_index()
            df_asig_long.columns = ["MES", "Codigo", "Cliente", "Asignado"]

            # 6.2 Reconstruir df_minimos con métricas
            df_min_m1 = df_min_pos.copy()  # solo MES=1 y códigos válidos
            df_min_m1["Asignado"] = df_min_m1.index.map(
                lambda idx: int(
                    df_asig_long[(df_asig_long["Codigo"] == idx[1]) & (df_asig_long["Cliente"] == idx[2])]["Asignado"].sum()
                )
            )
            df_min_m1["Cumple"] = df_min_m1["Asignado"] >= df_min_m1["Minimo"]
            df_min_m1["Pendiente Final"] = (df_min_m1["Minimo"] - df_min_m1["Asignado"]).clip(lower=0)

            # 6.3 Resumen por cliente
            resumen = df_min_m1.groupby(level=2).agg(
                Total_Minimo=("Minimo", "sum"),
                Total_Asignado=("Asignado", "sum")
            )
            resumen["% Cumplido"] = (resumen["Total_Asignado"] / resumen["Total_Minimo"] * 100).round(2)
            resumen.index = resumen.index.map(norm_cliente)
            resumen["Prioridad"] = resumen.index.map(prioridad_series.to_dict())
            resumen = resumen.sort_values(["Prioridad", "Total_Minimo"], ascending=[True, False])

            # =========================
            # 7) Excel de salida
            # =========================
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                # Asignación por mes (incluye PUSH)
                df_asig_out = df_asig_idx.reset_index()
                df_asig_out.to_excel(writer, sheet_name="Asignación Óptima", index=False)

                # Insumos
                df_stock.to_excel(writer, sheet_name="Stock Disponible", index=False)
                df_prior.to_excel(writer, sheet_name="Prioridad Clientes")

                # Mínimos con métricas
                df_min_export = df_min_m1.reset_index().rename(
                    columns={"level_0": "MES", "level_1": "Codigo", "level_2": "Cliente"}
                )
                df_min_export.to_excel(writer, sheet_name="Mínimos de Asignación", index=False)

                # Resumen Clientes
                resumen.reset_index(names="Cliente").to_excel(writer, sheet_name="Resumen Clientes", index=False)

            output.seek(0)
            st.success("✅ Asignación completada (v1.3.3).")

            # =========================
            # 8) Gráficos
            # =========================
            st.subheader("📊 Total asignado por cliente")
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            res_plot = resumen.sort_values("Total_Asignado", ascending=False)
            sns.barplot(x=res_plot.index, y=res_plot["Total_Asignado"], ax=ax1)
            ax1.set_title("Total Asignado por Cliente")
            ax1.set_ylabel("Unidades")
            ax1.set_xlabel("Cliente")
            ax1.tick_params(axis="x", rotation=45)
            st.pyplot(fig1)

            st.subheader("📈 Asignación por mes (suma de clientes)")
            df_mes = df_asig_idx.drop(columns=["PUSH"]).sum(axis=1).reset_index().groupby("MES")[0].sum().reset_index()
            df_mes.columns = ["MES", "Asignado"]
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            sns.barplot(data=df_mes, x="MES", y="Asignado", ax=ax2)
            ax2.set_title("Total Asignado por Mes")
            st.pyplot(fig2)

            st.subheader("📦 Stock sobrante asignado a PUSH por mes")
            df_push = df_asig_idx["PUSH"].groupby(level=0).sum().reset_index()
            df_push.columns = ["MES", "PUSH"]
            fig3, ax3 = plt.subplots(figsize=(8, 4))
            sns.barplot(data=df_push, x="MES", y="PUSH", ax=ax3)
            ax3.set_title("PUSH por Mes (Sobrantes)")
            st.pyplot(fig3)

            # =========================
            # 9) Descarga
            # =========================
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_PIAT_v1_3_3.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")

.
