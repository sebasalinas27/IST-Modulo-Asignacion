# =========================================================
# PIAS v1.4.2‑fix‑push — Políticas de mínimos seleccionables:
# 1) "Solo en un mes" (estricto por mes, sin arrastre, PUSH del mes)
# 2) "Continuo" (activable desde su mes, con arrastre)
#
# FIX v1.4.2‑fix (preservado):
# - Horizonte de meses = unión (meses en Stock ∪ meses en Mínimos > 0).
#   Permite activar/consumir cuotas aun cuando un mes no trae filas de stock.
# - Unión de códigos a procesar en continuo: set(carry) ∪ set(stock_mes.index).
#
# MEJORA solicitada (esta versión 'fix‑push'):
# - En "Continuo", el PUSH se registra en el/los mes(es) donde el CÓDIGO termina de asignar:
#   * Código SIN mínimos → PUSH mensual del remanente del mes (carry -> 0).
#   * Código CON mínimos → en su ÚLTIMO mes con mínimos y con 0 pendientes, PUSH del remanente de ese mes (carry -> 0).
#   * Fallback de seguridad al final por si quedara carry residual.
# =========================================================
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

# =========================
# 1) Cabecera de la App
# =========================
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST/PIAS - Asignación de Stock (v1.4.2‑fix‑push) - CH/MX/AR")
st.markdown("""
**Políticas de mínimos**
- **Solo en un mes**: cada mínimo del template se puede cumplir **únicamente** en su MES. El stock **no** se arrastra; sobrantes → **PUSH del mismo mes**.
- **Continuo**: cada mínimo se **activa** en su MES y puede cumplirse en meses futuros. El stock **sí** se arrastra (carry). El **PUSH** se registra cuando el **código termina** (ver mejora).

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
        requeridas_stock = {"MES", "Codigo", "Stock Disponible"}
        if not requeridas_stock.issubset(df_stock.columns):
            faltan = requeridas_stock - set(df_stock.columns)
            raise ValueError(f"La hoja 'Stock Disponible' debe contener las columnas: {', '.join(requeridas_stock)}. Faltan: {', '.join(faltan)}")

        # Stock
        df_stock["Codigo"] = df_stock["Codigo"].astype(str).str.strip()
        df_stock["MES"] = pd.to_numeric(df_stock["MES"], errors="coerce").fillna(1).astype(int)
        df_stock["Stock Disponible"] = pd.to_numeric(df_stock["Stock Disponible"], errors="coerce").fillna(0)
        df_stock = df_stock[df_stock["Stock Disponible"] > 0].copy()

        # Prioridades
        if df_prior.shape[1] < 1:
            raise ValueError("La hoja 'Prioridad Clientes' debe tener al menos una columna con el valor de prioridad.")
        prioridad_series = pd.to_numeric(df_prior.iloc[:, 0], errors="coerce").fillna(5).astype(int)
        prioridad_series.index = prioridad_series.index.map(lambda x: str(norm_cliente(x)))
        clientes_por_prioridad = prioridad_series.sort_values().index.tolist()

        # --- 3.3 Mínimos → conservar MES original y consolidar ---
        df_min = df_min.reset_index()
        df_min.columns = ["MES", "Codigo", "Cliente", "Minimo"]
        if "Minimo" not in df_min.columns:
            raise ValueError("La hoja 'Mínimos de Asignación' debe incluir la columna 'Minimo'.")
        df_min["MES"] = pd.to_numeric(df_min["MES"], errors="coerce").fillna(1).astype(int)
        df_min["Codigo"] = df_min["Codigo"].astype(str).str.strip()
        df_min["Cliente"] = df_min["Cliente"].map(lambda x: str(norm_cliente(x)))
        df_min["Minimo"] = pd.to_numeric(df_min["Minimo"], errors="coerce").fillna(0).astype(int)
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
        st.write(f"- **Productos en stock**: {df_stock['Codigo'].nunique():,}")
        st.write(f"- **Clientes con prioridad**: {df_prior.shape[0]:,}")
        st.write(f"- **Filas de mínimos (>0)**: {(df_min['Minimo'] > 0).sum():,}")
        st.info("Elige la política de mínimos y ejecuta la asignación.")

        # --- 3.6 Selector de política + ejecutar ---
        with st.form("run_asignacion"):
            modo = st.radio(
                "Política de mínimos",
                options=["Solo en un mes", "Continuo"],
                index=1,  # por defecto: Continuo
                horizontal=True,
                help=(
                    "Solo en un mes: cada mínimo solo se cumple en el MES indicado; el stock no se arrastra y el PUSH es del mismo mes. "
                    "Continuo: el mínimo se activa en su MES y puede cumplirse en meses posteriores; el stock se arrastra. "
                    "El PUSH se registra cuando el código termina."
                ),
            )
            ejecutar = st.form_submit_button("🔁 Ejecutar Asignación (según política elegida)")

        if ejecutar:
            # =========================
            # 4) Preparaciones comunes
            # =========================
            df_min_pos = df_min[df_min["Minimo"] > 0].copy()
            df_min_pos = df_min_pos[df_min_pos.index.get_level_values(1).isin(cod_validos)]

            # Meses a procesar = unión (stock ∪ mínimos>0)
            meses_stock = set(df_stock["MES"].unique())
            meses_min   = set(df_min_pos.reset_index()["MES"].unique()) if df_min_pos.shape[0] > 0 else set()
            meses = sorted(meses_stock | meses_min)
            mes_final = max(meses) if len(meses) else 1

            # Clientes presentes en mínimos, ordenados por prioridad
            clientes_en_min = sorted(
                {cli for (_, _, cli) in df_min_pos.index},
                key=lambda x: prioridad_series.get(x, 999)
            )

            # Columnas de salida (clientes + PUSH)
            columnas_asig = (
                [c for c in clientes_por_prioridad if c in clientes_en_min] +
                [c for c in clientes_en_min if c not in clientes_por_prioridad] +
                ["PUSH"]
            )

            # Estructuras de cuotas
            cuotas = {idx: _safe_int(q) for idx, q in df_min_pos["Minimo"].items()}
            asignado_cuota = {idx: 0 for idx in cuotas.keys()}

            # Índice FIFO por (Codigo, Cliente)
            cuotas_por_cod_cli = defaultdict(list)
            for (mes_obj, cod, cli), qty in cuotas.items():
                cuotas_por_cod_cli[(cod, cli)].append((mes_obj, qty, (mes_obj, cod, cli)))
            for k in cuotas_por_cod_cli:
                cuotas_por_cod_cli[k].sort(key=lambda t: t[0])  # FIFO por MES_obj

            # ======= Estructuras para "PUSH por término de código" =======
            last_mes_por_codigo = (
                df_min_pos.reset_index().groupby("Codigo")["MES"].max().to_dict()
            ) if df_min_pos.shape[0] > 0 else {}

            def pendientes_codigo(codigo: str) -> int:
                """Total pendiente en TODAS las cuotas del código."""
                total = 0
                for (mes_obj, cod, cli), qty in cuotas.items():
                    if cod != codigo:
                        continue
                    total += max(0, qty - asignado_cuota[(mes_obj, cod, cli)])
                return int(total)
            # =============================================================

            filas_salida = []  # builder de "Asignación Óptima"

            # =========================
            # 5) Motores de asignación
            # =========================
            def asignar_solo_en_su_mes():
                """Mínimos exigibles solo en su MES exacto. Stock no se arrastra. Sobrantes -> PUSH del mes."""
                for mes in meses:
                    stock_mes = (
                        df_stock[df_stock["MES"] == mes]
                        .groupby("Codigo")["Stock Disponible"].sum()
                    )
                    for codigo, stock_disp in stock_mes.items():
                        stock_disp = _safe_int(stock_disp)
                        asign_x_cliente = {c: 0 for c in columnas_asig}
                        if stock_disp <= 0:
                            filas_salida.append({"MES": mes, "Codigo": codigo, **{c: 0.0 for c in columnas_asig}})
                            continue
                        for cliente in columnas_asig:
                            if cliente == "PUSH" or stock_disp <= 0:
                                continue
                            lst = cuotas_por_cod_cli.get((codigo, cliente), [])
                            for (mes_obj, qty, idx_key) in lst:
                                if mes_obj != mes:
                                    continue
                                pendiente = qty - asignado_cuota[idx_key]
                                if pendiente <= 0 or stock_disp <= 0:
                                    continue
                                asign = min(pendiente, stock_disp)
                                asignado_cuota[idx_key] += asign
                                stock_disp -= asign
                                asign_x_cliente[cliente] += asign
                                if stock_disp <= 0:
                                    break
                        if stock_disp > 0:
                            asign_x_cliente["PUSH"] += float(stock_disp)
                        filas_salida.append({"MES": mes, "Codigo": codigo, **asign_x_cliente})

            def asignar_continuo():
                """
                Mínimos activables desde su MES y consumibles hacia adelante. Stock se arrastra (carry).
                MEJORA: el PUSH se registra en el mes donde el CÓDIGO termina de asignar.
                  - Código SIN mínimos → PUSH mensual (todo lo disponible del mes + carry).
                  - Código CON mínimos → en su último mes y con 0 pendientes, remanente a PUSH del mes.
                """
                carry_stock = {}  # stock arrastrable por código
                codigos_con_min = set(df_min_pos.index.get_level_values(1)) if df_min_pos.shape[0] > 0 else set()

                for mes in meses:
                    stock_mes = (
                        df_stock[df_stock["MES"] == mes]
                        .groupby("Codigo")["Stock Disponible"].sum()
                    )
                    # acumular llegadas
                    for codigo, inc in stock_mes.items():
                        carry_stock[codigo] = carry_stock.get(codigo, 0) + _safe_int(inc)

                    # procesar códigos con carry o llegadas (UNIÓN)
                    codigos_trabajo = set(carry_stock.keys()) | set(stock_mes.index)

                    for codigo in sorted(codigos_trabajo):
                        asign_x_cliente = {c: 0 for c in columnas_asig}

                        # repartir a cuotas activas (MES_obj <= mes)
                        if carry_stock.get(codigo, 0) > 0:
                            for cliente in columnas_asig:
                                if cliente == "PUSH":
                                    continue
                                if carry_stock[codigo] <= 0:
                                    break
                                lst = cuotas_por_cod_cli.get((codigo, cliente), [])
                                if not lst:
                                    continue
                                for (mes_obj, qty, idx_key) in lst:
                                    if mes_obj > mes:
                                        break  # aún no activada
                                    pendiente = qty - asignado_cuota[idx_key]
                                    if pendiente <= 0:
                                        continue
                                    if carry_stock[codigo] <= 0:
                                        break
                                    asign = min(pendiente, carry_stock[codigo])
                                    asignado_cuota[idx_key] += asign
                                    carry_stock[codigo] -= asign
                                    asign_x_cliente[cliente] += asign
                                    if carry_stock[codigo] <= 0:
                                        break

                        # --- DECISIÓN DE PUSH DEL MES (MEJORA) ---
                        tiene_min = codigo in codigos_con_min
                        if not tiene_min:
                            # sin mínimos → PUSH mensual
                            if carry_stock.get(codigo, 0) > 0:
                                asign_x_cliente["PUSH"] += float(carry_stock[codigo])
                                carry_stock[codigo] = 0
                        else:
                            # con mínimos → último mes y 0 pendientes
                            last_mes = last_mes_por_codigo.get(codigo, None)
                            if last_mes is not None and mes >= int(last_mes):
                                if carry_stock.get(codigo, 0) > 0 and pendientes_codigo(codigo) == 0:
                                    asign_x_cliente["PUSH"] += float(carry_stock[codigo])
                                    carry_stock[codigo] = 0

                        # registrar fila si hubo asignación o recepción de stock
                        if any(asign_x_cliente[c] > 0 for c in columnas_asig) or (codigo in stock_mes.index):
                            filas_salida.append({"MES": mes, "Codigo": codigo, **asign_x_cliente})

                    # limpieza opcional de carry
                    for codigo in list(carry_stock.keys()):
                        if carry_stock[codigo] <= 0 and codigo not in stock_mes.index:
                            del carry_stock[codigo]

                # Fallback de seguridad
                for codigo, rem in carry_stock.items():
                    rem = _safe_int(rem)
                    if rem > 0:
                        filas_salida.append({"MES": mes_final, "Codigo": codigo, **{c: 0.0 for c in columnas_asig}, "PUSH": float(rem)})

            # --- Ejecutar el motor elegido ---
            if modo == "Solo en un mes":
                asignar_solo_en_su_mes()
            else:
                asignar_continuo()

            # =========================
            # 6) Armar DataFrame de salida y métricas
            # =========================
            if len(filas_salida) == 0:
                df_asig = pd.DataFrame(columns=["MES", "Codigo"] + columnas_asig)
                df_asig_idx = df_asig.set_index(["MES", "Codigo"])
            else:
                df_asig = pd.DataFrame(filas_salida)
                for c in columnas_asig:
                    if c not in df_asig.columns:
                        df_asig[c] = 0.0
                df_asig = df_asig.fillna(0)
                df_asig_idx = (
                    df_asig.groupby(["MES", "Codigo"], as_index=True)[columnas_asig]
                    .sum()
                    .sort_index()
                )
            df_asig_idx = df_asig_idx.reindex(columns=columnas_asig).fillna(0)

            # Métricas por fila del template
            df_min_metrics = df_min_pos.copy()
            df_min_metrics["Asignado"] = df_min_metrics.index.map(lambda idx: _safe_int(asignado_cuota.get(idx, 0)))
            df_min_metrics["Cumple"] = df_min_metrics["Asignado"] >= df_min_metrics["Minimo"]
            df_min_metrics["Pendiente Final"] = (df_min_metrics["Minimo"] - df_min_metrics["Asignado"]).clip(lower=0)

            # =========================
            # 7) Excel de salida (mismas hojas)
            # =========================
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asig_out = df_asig_idx.reset_index()
                df_asig_out.to_excel(writer, sheet_name="Asignación Óptima", index=False)
                df_stock.to_excel(writer, sheet_name="Stock Disponible", index=False)
                df_prior.to_excel(writer, sheet_name="Prioridad Clientes")
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
                df_mes = (
                    df_asig_idx.drop(columns=["PUSH"]).sum(axis=1).reset_index()
                    .groupby("MES")[0].sum().reset_index()
                )
            else:
                df_mes = (
                    df_asig_idx.sum(axis=1).reset_index()
                    .groupby("MES")[0].sum().reset_index()
                )
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
                file_name="asignacion_resultados_PIAT_v1_4_2_fix_push.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
