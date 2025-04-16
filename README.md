# 📦 IST - Módulo de Asignación (PIAT v1.3)

Este proyecto optimiza la asignación de stock por cliente y por mes, considerando prioridades, mínimos requeridos y aprovechando el stock total mediante programación lineal.

---

## ✅ ¿Qué hace este módulo?

- Asigna productos considerando **mínimos requeridos por cliente y mes**
- Utiliza el **stock restante de meses anteriores**
- Prioriza clientes por nivel definido (1 es mayor prioridad)
- Aprovecha el stock no solicitado asignándolo a un cliente **ficticio PUSH**
- Calcula el **% de cumplimiento** por cliente y reporta pendientes
- Exporta un archivo Excel con todas las vistas necesarias

---

## 🧩 Cómo usar

1. Sube el archivo Excel con las siguientes hojas:
   - `Stock Disponible`
   - `Mínimos de Asignación`
   - `Prioridad Clientes`
2. Presiona **Ejecutar Asignación**
3. Descarga el archivo con los resultados

---

## 📂 Salida generada

- **Asignación Óptima** → qué producto fue asignado a qué cliente y en qué mes
- **Stock Disponible** → stock original, restante y arrastrado
- **Prioridad Clientes** → prioridades procesadas
- **Mínimos de Asignación** → comparativo de mínimo vs asignado
- **Resumen Clientes** → total mínimo, asignado y % de cumplimiento

---

## 🛠 Tecnologías

- Construido en **Python**
- Librerías: `Pandas`, `NumPy`, `Streamlit`, `XlsxWriter`
- Interfaz 100% en **Streamlit Web App**

🔗 [Accede al módulo en línea](https://ist-modulo-asignacion-kyb553dzoqlfpcfjccfxdt.streamlit.app/)

📁 [Repositorio GitHub](https://github.com/sebasalinas27/IST-Modulo-Asignacion)

---

## 🚀 Última versión: **PIAT v1.3**
- ✔️ Arrastre de pendientes
- ✔️ Cliente PUSH
- ✔️ Validación completa
- ✔️ Excel con 5 hojas y resumen visual
