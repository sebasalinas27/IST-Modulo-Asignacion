# =========================================================
# PIAT v1.4.0 — Políticas de mínimos seleccionables:
#   1) "Solo en su mes" (estricto por mes, sin arrastre, PUSH del mes)
#   2) "Continuo (desde su mes hacia adelante)" (activable, con arrastre, PUSH final)
#
# Reglas generales:
# - El template de "Mínimos de Asignación" define filas: (MES, Codigo, Cliente, Minimo).
# - En "Solo en su mes": cada fila SOLO puede cubrirse en su MES exacto.
# - En "Continuo": cada fila se activa en su MES y puede seguir cubriéndose en meses posteriores.
# - La prioridad (1 = mayor) define el orden de asignación entre clientes por código.
# - "PUSH" recibe sobrantes: en el estricto, por mes; en el continuo, sólo al final (último mes).
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
st.title("📦 IST/PIAT - Asignación de Stock (v1.4.0) Chile-México-Argentina")

st.markdown("""
**Políticas disponibles**
- **Solo en su mes**: cada mínimo de la hoja *Mínimos de Asignación* se puede cumplir **únicamente** en su MES. El stock **no** se arrastra; sobrantes → **PUSH del mismo mes**.
- **Continuo (desde su mes hacia adelante)**: cada mínimo se **activa** en su MES y puede cumplirse en meses futuros. El stock **sí** se arrastra (carry) y **PUSH** se liquida **solo al final**.

**Estructura del archivo Excel:**
- **Stock Disponible** → columnas: `MES`, `Codigo`, `Stock Disponible`
- **Mínimos de Asignación** → índice: `MES`, `Codigo`, `Cliente`; columna `Minimo`
- **Prioridad Clientes** → índice: `Cliente`; valor: prioridad (1 = mayor)
""")

uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

# =========================
# 2) Helpers
# =========================
def norm_cliente(x):
    return x.strip() if isinstance(x, str) else x

def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default

# =========================
# 3) Proceso principal
# =========================
if uploaded_file:
    try:
        # --- 3.1 Carga de hojas ---
        df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
        df_prior = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
        df_min   = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0, 1, 2])

        # --- 3.2 Limpieza mínima ---
        df_stock.columns = [c.strip() for c in df_stock.columns]
        if not {"MES", "Codigo", "Stock Disponible"}.issubset(set(df_stock.columns)):
            raise ValueError("La hoja 'Stock Disponible' debe contener las columnas: MES, Codigo, Stock Disponible.")

        df_stock["Codigo"] = df_stock["Codigo"].astype(str).str.strip()
        df_stock["MES"] = pd.to_numeric(df_stock["MES"], errors="coerce").fillna(1).astype(int)
        df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()

        # Prioridades
        if df_prior.shape[1] < 1:
            raise ValueError("La hoja 'Prioridad Clientes' debe tener al menos una columna con el valor de prioridad.")
        prioridad_series = pd.to_numeric(df_prior.iloc[:, 0], errors="coerce").fillna(5).astype(int)
        prioridad_series.index = prioridad_series.index.map(norm_cliente)
        clientes_por_prioridad = prioridad_series.sort_values().index.tolist()

        # --- 3.3 Mínimos → conservar MES original y consolidar ---
        df_min = df_min.reset_index()
        df_min.columns = ["MES", "Codigo", "Cliente", "Minimo"]
        if "Minimo" not in df_min.columns:
            raise ValueError("La hoja 'Mínimos de Asignación' debe incluir la columna 'Minimo'.")

        df_min["MES"] = pd.to_numeric(df_min["MES"], errors="coerce").fillna(1).astype(int)
        df_min["Codigo"] = df_min["Codigo"].astype(str).str.strip()
        df_min["Cliente"] = df_min["Cliente"].map(norm_cliente)

        # Consolidar posibles duplicados exactos de (MES, Codigo, Cliente)
        df_min = (
            df_min.groupby(["MES", "Codigo", "Cliente"], as_index=True)["Minimo"]
                  .sum()
                  .to_frame()
        )

        # --- 3.4 Intersección de códigos válidos ---
        cod_min = set(df_min.index.get_level_values(1))
        cod_stk = set(df_stock["Codigo"])
        cod_validos = sorted(cod_min & cod_stk)

        # --- 3.5 Resumen de entrada ---
        st.subheader("📊 Resumen del archivo cargado")
        st.write(f"- **Productos en stock**: {df_stock['Codigo'].nunique()}")
        st.write(f"- **Clientes con prioridad**: {df_prior.shape[0]}")
        st.write(f"- **Filas de mínimos (>0)**: {(df_min['Minimo'] > 0).sum()}")

        st.info("Elige la política de mínimos y ejecuta la asignación.")

        # --- 3.6 Selector de política + ejecutar ---
        with st.form("run_asignacion"):
            modo = st.radio(
                "Política de mínimos",
                options=["Solo en su mes", "Continuo (desde su mes hacia adelante)"],
                index=1,  # por defecto: continuo
                horizontal=True,
                help=(
                    "Solo en su mes: cada mínimo solo se cumple en el MES indicado; el stock no se arrastra y el PUSH es del mismo mes. "
                    "Continuo: el mínimo se activa en su MES y puede cumplirse en meses posteriores; el stock se arrastra y el PUSH es solo al final."
                ),
            )
            ejecutar = st.form_submit_button("🔁 Ejecutar Asignación (según política elegida)")

        if ejecutar:
            # =========================
            # 4) Preparaciones comunes
            # =========================
            # Mínimos positivos y con código válido
            df_min_pos = df_min[df_min["Minimo"] > 0].copy()
            df_min_pos = df_min_pos[df_min_pos.index.get_level_values(1).isin(cod_validos)]

            # Meses a procesar y columnas de salida (clientes presentes en mínimos)
            meses = sorted(df_stock["MES"].unique())
            mes_final = max(meses) if len(meses) else 1

            clientes_en_min = sorted(
                {cli for (_, _, cli) in df_min_pos.index},
                key=lambda x: prioridad_series.get(x, 999)
            )
            columnas_asig = (
                [c for c in clientes_por_prioridad if c in clientes_en_min] +
                [c for c in clientes_en_min if c not in clientes_por_prioridad] +
                ["PUSH"]
            )

            # DataFrame de salida vacío con índice MultiIndex (MES, Codigo)
            idx_empty = pd.MultiIndex.from_arrays([[], []], names=["MES", "Codigo"])
            df_asig = pd.DataFrame(columns=columnas_asig, index=idx_empty, dtype=float)

            # Cada fila del template es una "obligación": (MES_obj, Codigo, Cliente) -> cantidad
            cuotas = { idx: _safe_int(q) for idx, q in df_min_pos["Minimo"].items() }
            asignado_cuota = { idx: 0 for idx in cuotas.keys() }

            # =========================
            # 5) Motores de asignación
            # =========================
            def asignar_solo_en_su_mes():
                """Mínimos exigibles solo en su MES exacto. Stock no se arrastra. Sobrantes -> PUSH del mes."""
                for mes in meses:
                    stock_mes = (
                        df_stock[df_stock["MES"] == mes]
                        .groupby("Codigo")["Stock Disponible"]
                        .sum()
                    )
                    # Recorre códigos con stock en este mes
                    for codigo, stock_disp in stock_mes.items():
                        stock_disp = _safe_int(stock_disp)
                        fila = pd.Series(0, index=columnas_asig, dtype=float)

                        # ¿Existen mínimos para este (MES, Codigo)?
                        tiene_cuotas_mes = any((mes, codigo, cli) in cuotas for cli in clientes_en_min)

                        if not tiene_cuotas_mes:
                            # No hay mínimos este mes para este código => todo a PUSH del mes
                            if stock_disp > 0:
                                fila["PUSH"] = float(stock_disp)
                            df_asig.loc[(mes, codigo), columnas_asig] = fila.values
                            continue

                        # Reparto por prioridad (clientes)
                        for cliente in columnas_asig:
                            if cliente == "PUSH" or stock_disp <= 0:
                                continue
                            idx = (mes, codigo, cliente)
                            if idx not in cuotas:
                                continue
                            pendiente = cuotas[idx] - asignado_cuota[idx]
                            if pendiente <= 0:
                                continue
                            asign = min(pendiente, stock_disp)
                            asignado_cuota[idx] += asign
                            stock_disp -= asign
                            fila[cliente] += asign

                        # Sobrante del mes va a PUSH del mismo mes
                        if stock_disp > 0:
                            fila["PUSH"] += float(stock_disp)

                        df_asig.loc[(mes, codigo), columnas_asig] = fila.values

            def asignar_continuo():
                """Mínimos activables desde su MES y consumibles hacia adelante. Stock se arrastra. PUSH solo al final."""
                carry_stock = {}  # stock arrastrable por código

                for mes in meses:
                    # Sumar stock del mes al carry por código
                    stock_mes = (
                        df_stock[df_stock["MES"] == mes]
                        .groupby("Codigo")["Stock Disponible"]
                        .sum()
                    )
                    for codigo, inc in stock_mes.items():
                        carry_stock[codigo] = carry_stock.get(codigo, 0) + _safe_int(inc)

                    # Trabajar todos los códigos que tengan carry o aparezcan en el stock global
                    codigos_trabajo = set(carry_stock.keys()) | set(df_stock["Codigo"].unique())

                    for codigo in sorted(codigos_trabajo):
                        fila = pd.Series(0, index=columnas_asig, dtype=float)

                        # Si no hay stock acumulado, registrar fila 0 para traza (si quieres, se podría omitir)
                        if carry_stock.get(codigo, 0) <= 0:
                            df_asig.loc[(mes, codigo), columnas_asig] = fila.values
                            continue

                        # Reparto por prioridad: cuotas ACTIVAS (MES_obj <= mes) con saldo
                        for cliente in columnas_asig:
                            if cliente == "PUSH":
                                continue
                            if carry_stock[codigo] <= 0:
                                break

                            # Todas las cuotas activas de este cliente y código (FIFO por MES_obj)
                            cuotas_activas = sorted(
                                [idx for idx in cuotas.keys()
                                 if idx[1] == codigo and idx[2] == cliente and idx[0] <= mes
                                 and asignado_cuota[idx] < cuotas[idx]],
                                key=lambda idx: idx[0]
                            )

                            for idx in cuotas_activas:
                                if carry_stock[codigo] <= 0:
                                    break
                                pendiente = cuotas[idx] - asignado_cuota[idx]
                                if pendiente <= 0:
                                    continue
                                asign = min(pendiente, carry_stock[codigo])
                                asignado_cuota[idx] += asign
                                carry_stock[codigo] -= asign
                                fila[cliente] += asign

                        # Guardar asignaciones de este mes para este código
                        df_asig.loc[(mes, codigo), columnas_asig] = fila.values

                # Al finalizar todos los meses → PUSH final (solo en el último MES) con lo que haya quedado en carry
                for codigo, rem in carry_stock.items():
                    rem = _safe_int(rem)
                    if rem > 0:
                        if (mes_final, codigo) not in df_asig.index:
                            df_asig.loc[(mes_final, codigo), columnas_asig] = 0
                        df_asig.loc[(mes_final, codigo), "PUSH"] = df_asig.loc[(mes_final, codigo), "PUSH"] + float(rem)

            # --- Ejecutar el motor elegido ---
            if modo == "Solo en su mes":
                asignar_solo_en_su_mes()
            else:
                asignar_continuo()

            # Blindaje final: mismas columnas y sin NaN
            df_asig = df_asig.reindex(columns=columnas_asig).fillna(0)

            # =========================
            # 6) Métricas por fila del template (misma hoja de salida)
            # =========================
            df_min_metrics = df_min_pos.copy()
            df_min_metrics["Asignado"] = df_min_metrics.index.map(lambda idx: _safe_int(asignado_cuota.get(idx, 0)))
            df_min_metrics["Cumple"] = df_min_metrics["Asignado"] >= df_min_metrics["Minimo"]
            df_min_metrics["Pendiente Final"] = (df_min_metrics["Minimo"] - df_min_metrics["Asignado"]).clip(lower=0)

            # =========================
            # 7) Excel de salida (mismas hojas)
            # =========================
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                # Asignación por mes (incluye PUSH)
                df_asig_out = df_asig.reset_index()
                df_asig_out.to_excel(writer, sheet_name="Asignación Óptima", index=False)

                # Insumos
                df_stock.to_excel(writer, sheet_name="Stock Disponible", index=False)
                df_prior.to_excel(writer, sheet_name="Prioridad Clientes")

                # Mínimos de Asignación con métricas por fila
                df_min_export = df_min_metrics.reset_index().rename(
                    columns={"level_0": "MES", "level_1": "Codigo", "level_2": "Cliente"}
                )
                df_min_export.to_excel(writer, sheet_name="Mínimos de Asignación", index=False)

            output.seek(0)
            st.success(f"✅ Asignación completada — Política: {modo}")

            # =========================
            # 8) Gráficos
            # =========================
            st.subheader("📊 Total asignado por cliente")
            df_asig_idx = df_asig.copy()
            if "PUSH" in df_asig_idx.columns:
                df_asig_long = df_asig_idx.drop(columns=["PUSH"]).stack().reset_index()
            else:
                df_asig_long = df_asig_idx.stack().reset_index()
            df_asig_long.columns = ["MES", "Codigo", "Cliente", "Asignado"]

            fig1, ax1 = plt.subplots(figsize=(10, 4))
            res_plot = df_asig_long.groupby("Cliente")["Asignado"].sum().sort_values(ascending=False)
            if len(res_plot) > 0:
                sns.barplot(x=res_plot.index, y=res_plot.values, ax=ax1)
            ax1.set_title("Total Asignado por Cliente")
            ax1.set_ylabel("Unidades")
            ax1.set_xlabel("Cliente")
            ax1.tick_params(axis="x", rotation=45)
            st.pyplot(fig1)

            st.subheader("📈 Asignación por mes (suma de clientes)")
            if "PUSH" in df_asig_idx.columns:
                df_mes = (df_asig_idx.drop(columns=["PUSH"]).sum(axis=1).reset_index()
                          .groupby("MES")[0].sum().reset_index())
            else:
                df_mes = df_asig_idx.sum(axis=1).reset_index().groupby("MES")[0].sum().reset_index()
            df_mes.columns = ["MES", "Asignado"]
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            if df_mes.shape[0] > 0:
                sns.barplot(data=df_mes, x="MES", y="Asignado", ax=ax2)
            ax2.set_title("Total Asignado por Mes")
            st.pyplot(fig2)

            st.subheader("📦 PUSH por mes")
            if "PUSH" in df_asig_idx.columns:
                df_push = df_asig_idx["PUSH"].groupby(level=0).sum().reset_index()
                df_push.columns = ["MES", "PUSH"]
            else:
                df_push = pd.DataFrame({"MES": [], "PUSH": []})
            fig3, ax3 = plt.subplots(figsize=(8, 4))
            if df_push.shape[0] > 0:
                sns.barplot(data=df_push, x="MES", y="PUSH", ax=ax3)
            ax3.set_title("PUSH por Mes")
            st.pyplot(fig3)

            # =========================
            # 9) Descarga
            # =========================
            st.download_button(
                label="📥 Descargar archivo Excel",
                data=output.getvalue(),
                file_name="asignacion_resultados_PIAT_v1_4_0.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
