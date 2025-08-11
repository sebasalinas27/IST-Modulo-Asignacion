# ----------------------------------------------------
# 1. CARGA DE LIBRERÍAS
# ----------------------------------------------------
import pandas as pd
import numpy as np

# ----------------------------------------------------
# 2. CARGA DEL ARCHIVO EXCEL
# ----------------------------------------------------
archivo = "Template Chile 1.xlsx"

df_stock = pd.read_excel(archivo, sheet_name="Stock Disponible")
df_minimos = pd.read_excel(archivo, sheet_name="Mínimos de Asignación")
df_prioridad = pd.read_excel(archivo, sheet_name="Prioridad Clientes")

# ----------------------------------------------------
# 3. NORMALIZACIÓN DE LOS MÍNIMOS A MES 1
# ----------------------------------------------------
# Todos los mínimos se asignan al mes 1, sin importar el mes original
df_minimos["Mes"] = 1

# ----------------------------------------------------
# 4. VALIDACIÓN DE DATOS
# ----------------------------------------------------
# Evitar duplicados por código-cliente-mes
df_minimos = df_minimos.drop_duplicates(subset=["Codigo", "Cliente", "Mes"])

# Filtrar solo códigos que existan en stock
df_minimos = df_minimos[df_minimos["Codigo"].isin(df_stock["Codigo"])]

# ----------------------------------------------------
# 5. MERGE DE PRIORIDAD
# ----------------------------------------------------
df_minimos = df_minimos.merge(
    df_prioridad[["Cliente", "Prioridad"]],
    on="Cliente",
    how="left"
)

# ----------------------------------------------------
# 6. ORDENAMIENTO POR PRIORIDAD
# ----------------------------------------------------
df_minimos = df_minimos.sort_values(by=["Prioridad", "Cliente", "Codigo"])

# ----------------------------------------------------
# 7. ASIGNACIÓN DE STOCK SEGÚN MÍNIMOS
# ----------------------------------------------------
# Convertir a tabla pivote para manejar más fácil
pivot_minimos = df_minimos.pivot_table(
    index="Codigo",
    columns="Cliente",
    values="Minimo",
    fill_value=0
)

# Crear DataFrame de asignaciones iniciales
asignacion = pivot_minimos.copy()

# Ajustar stock por fila
for codigo in asignacion.index:
    stock_disp = df_stock.loc[df_stock["Codigo"] == codigo, "Stock Disponible"].values[0]
    suma_minimos = asignacion.loc[codigo].sum()

    if suma_minimos <= stock_disp:
        # Se asignan todos los mínimos y el resto se ignora aquí
        continue
    else:
        # Distribuir proporcionalmente el stock disponible
        proporciones = asignacion.loc[codigo] / suma_minimos
        asignacion.loc[codigo] = np.floor(proporciones * stock_disp)

# ----------------------------------------------------
# 8. SALIDA FINAL
# ----------------------------------------------------
asignacion_reset = asignacion.reset_index()
asignacion_reset.to_excel("Asignacion_Mes_Unico.xlsx", index=False)
print("✅ Asignación generada: Asignacion_Mes_Unico.xlsx")
