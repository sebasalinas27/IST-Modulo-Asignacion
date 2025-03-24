#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Muestra de excel

import pandas as pd
import numpy as np

# Parámetros del template
num_codigos = 100
num_clientes = 20
num_meses = 4

# Generar lista de códigos (ZAP001, ZAP002, ...)
codigos = [f"ZAP{str(i+1).zfill(3)}" for i in range(num_codigos)]

# Generar lista de clientes (Cliente A, Cliente B, ...)
clientes = [f"Cliente {chr(65+i)}" for i in range(num_clientes)]

# Generar lista de meses (1, 2, 3, 4)
meses = list(range(1, num_meses + 1))

# Crear DataFrame de 'Stock Disponible'
stock_data = []
for mes in meses:
    for codigo in codigos:
        stock_disponible = np.random.randint(50, 500)  # Stock aleatorio entre 50 y 500 unidades
        stock_data.append([mes, codigo, stock_disponible])

df_stock = pd.DataFrame(stock_data, columns=["MES", "Codigo", "Stock Disponible"])

# Crear DataFrame de 'Mínimos de Asignación'
minimos_data = []
for mes in meses:
    for codigo in codigos:
        for cliente in clientes:
            minimo_requerido = np.random.choice([0, np.random.randint(5, 50)], p=[0.5, 0.5])  # 50% de chance de requerir un mínimo
            minimos_data.append([mes, codigo, cliente, minimo_requerido])

df_minimos = pd.DataFrame(minimos_data, columns=["MES", "Codigo", "Cliente", "Minimo"])

# Crear DataFrame de 'Prioridad Clientes'
prioridad_data = [[cliente, np.random.randint(1, 6)] for cliente in clientes]  # Prioridad entre 1 y 5
df_prioridad = pd.DataFrame(prioridad_data, columns=["Cliente", "Prioridad"])

# Guardar en un archivo Excel
template_path = "Template_Pruebas_PIAT.xlsx"
with pd.ExcelWriter(template_path) as writer:
    df_stock.to_excel(writer, sheet_name="Stock Disponible", index=False)
    df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación", index=False)
    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes", index=False)

print(f"✅ Template generado con éxito en '{template_path}'")


# In[2]:


# Codigo 1

import numpy as np
import pandas as pd

# 💕 Rutas de archivos de entrada y salida
entrada_path = "Template_Pruebas_PIAT.xlsx"
salida_path = "asignacion_resultados_completo.xlsx"

# 🔹 1. Cargar datos
df_stock = pd.read_excel(entrada_path, sheet_name='Stock Disponible')
df_prioridad = pd.read_excel(entrada_path, sheet_name='Prioridad Clientes', index_col=0)
df_minimos = pd.read_excel(entrada_path, sheet_name='Mínimos de Asignación', index_col=[0, 1, 2])

# 🔹 2. Filtrar datos innecesarios
# Filtrar productos con stock disponible
df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].set_index(['MES', 'Codigo']).sort_index()

# Filtrar códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'
codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)).intersection(df_minimos.index.get_level_values(1))
if not codigos_comunes:
    raise ValueError("❌ No se encontraron códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'. Verifica los datos.")

# Ordenar clientes por prioridad
prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

# 🔹 3. Asignación por MES y prioridad
df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']
df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

# Obtener la lista de meses ordenados
meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

for mes in meses_ordenados:
    df_stock_mes = df_stock_filtrado.loc[mes]
    df_minimos_mes = df_minimos.loc[mes] if mes in df_minimos.index else pd.DataFrame()

    for cliente in clientes_ordenados:
        for codigo in df_stock_mes.index:
            minimo_requerido = df_minimos_mes.loc[(codigo, cliente), 'Minimo'] if (codigo, cliente) in df_minimos_mes.index else 0
            stock_disponible = df_stock_mes.at[codigo, 'Stock Restante']

            if minimo_requerido > 0:
                if stock_disponible >= minimo_requerido:
                    df_asignacion.at[(mes, codigo), cliente] = minimo_requerido
                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= minimo_requerido
                else:
                    df_asignacion.at[(mes, codigo), cliente] = stock_disponible
                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] = 0

# Guardar resultados
with pd.ExcelWriter(salida_path) as writer:
    df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
    df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
    df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")

print(f"✅ Optimización completada. Resultados guardados en '{salida_path}'.")


# In[2]:


# Codigo 2
import numpy as np
import pandas as pd

# 💕 Rutas de archivos de entrada y salida
entrada_path = "Template_Pruebas_PIAT.xlsx"
salida_path = "asignacion_resultados_completo.xlsx"

# 🔹 1. Cargar datos
df_stock = pd.read_excel(entrada_path, sheet_name='Stock Disponible')
df_prioridad = pd.read_excel(entrada_path, sheet_name='Prioridad Clientes', index_col=0)
df_minimos = pd.read_excel(entrada_path, sheet_name='Mínimos de Asignación', index_col=[0, 1, 2])

# 🔹 2. Filtrar datos innecesarios
# Filtrar productos con stock disponible
df_stock_filtrado = df_stock[df_stock['Stock Disponible'] > 0].set_index(['MES', 'Codigo']).sort_index()

# Filtrar códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'
codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)).intersection(df_minimos.index.get_level_values(1))
if not codigos_comunes:
    raise ValueError("❌ No se encontraron códigos comunes entre 'Stock Disponible' y 'Mínimos de Asignación'. Verifica los datos.")

# Ordenar clientes por prioridad
prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
clientes_ordenados = prioridad_clientes.sort_values().index.tolist()

# 🔹 3. Ajuste del stock disponible incluyendo remanente del mes anterior
df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']
meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())

for mes in meses_ordenados:
    if mes > 1:
        stock_anterior = df_stock_filtrado.loc[(mes - 1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
        df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'] = df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'].fillna(0) + stock_anterior.reindex(df_stock_filtrado.loc[(mes, slice(None))].index, fill_value=0).values
    df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

# 🔹 4. Asignación por MES y prioridad
df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

for mes in meses_ordenados:
    df_stock_mes = df_stock_filtrado.loc[mes]
    df_minimos_mes = df_minimos.loc[mes] if mes in df_minimos.index else pd.DataFrame()

    for cliente in clientes_ordenados:
        for codigo in df_stock_mes.index:
            minimo_requerido = df_minimos_mes.loc[(codigo, cliente), 'Minimo'] if (codigo, cliente) in df_minimos_mes.index else 0
            stock_disponible = df_stock_mes.at[codigo, 'Stock Restante']

            if minimo_requerido > 0:
                if stock_disponible >= minimo_requerido:
                    df_asignacion.at[(mes, codigo), cliente] = minimo_requerido
                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] -= minimo_requerido
                else:
                    df_asignacion.at[(mes, codigo), cliente] = stock_disponible
                    df_stock_filtrado.at[(mes, codigo), 'Stock Restante'] = 0

# Guardar resultados
with pd.ExcelWriter(salida_path) as writer:
    df_asignacion.to_excel(writer, sheet_name="Asignación Óptima")
    df_stock_filtrado.to_excel(writer, sheet_name="Stock Disponible")
    df_prioridad.to_excel(writer, sheet_name="Prioridad Clientes")
    df_minimos.to_excel(writer, sheet_name="Mínimos de Asignación")

print(f"✅ Optimización completada. Resultados guardados en '{salida_path}'.")



# In[ ]:




