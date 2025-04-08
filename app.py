# 🔁 Verificar si hay códigos comunes válidos
codigos_comunes = set(df_stock_filtrado.index.get_level_values(1)).intersection(df_minimos.index.get_level_values(1))

if len(codigos_comunes) == 0:
    st.warning("⚠️ No hay códigos en común entre stock y mínimos. Se continuará sin asignaciones.")
    df_asignacion = pd.DataFrame(0, index=pd.MultiIndex.from_tuples([], names=["MES", "Codigo"]), columns=df_prioridad.index)
else:
    codigos_validos = df_stock_filtrado.index[df_stock_filtrado.index.get_level_values(1).isin(codigos_comunes)]
    df_stock_filtrado = df_stock_filtrado.loc[codigos_validos]

    prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:, 0], errors='coerce').fillna(0)
    clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
    df_asignacion = pd.DataFrame(0, index=df_minimos.index.droplevel(2).unique(), columns=clientes_ordenados)

    meses_ordenados = sorted(df_stock_filtrado.index.get_level_values(0).unique())
    df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

    for mes in meses_ordenados:
        if mes > 1:
            stock_anterior = df_stock_filtrado.loc[(mes - 1, slice(None)), 'Stock Restante'].groupby(level=1).sum()
            df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'] = df_stock_filtrado.loc[(mes, slice(None)), 'Stock Disponible'].fillna(0) + stock_anterior.reindex(df_stock_filtrado.loc[(mes, slice(None))].index, fill_value=0).values
        df_stock_filtrado['Stock Restante'] = df_stock_filtrado['Stock Disponible']

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
