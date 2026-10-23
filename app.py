import streamlit as st
import pandas as pd
import graphviz

# ==========================================
# CONFIGURACIÓN PROFESIONAL DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Balanceo de Línea RPP", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado para un aspecto más limpio
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("⚙️ Balanceo de Línea por Método RPP")
st.markdown("Calcula estaciones de trabajo, eficiencia y genera diagramas de precedencia automáticamente.")

# ==========================================
# BARRA LATERAL: PARÁMETROS OPERATIVOS
# ==========================================
with st.sidebar:
    st.header("📊 Parámetros de Turno")
    demanda = st.number_input("Demanda Diaria (unidades)", min_value=1, value=25)
    horas_turno = st.number_input("Horas por Turno", min_value=1.0, value=8.0, step=0.5)
    paros = st.number_input("Tiempos de Paro (min)", min_value=0, value=5)
    
    st.divider()
    
    tiempo_disp = horas_turno * 60
    tiempo_operativo = tiempo_disp - paros
    tiempo_ciclo = tiempo_operativo / demanda if demanda > 0 else 0
    
    st.metric("Tiempo Operativo", f"{tiempo_operativo:,.0f} min")
    st.metric("Tiempo de Ciclo Máximo", f"{tiempo_ciclo:,.2f} min/u")

# ==========================================
# SECCIÓN CENTRAL: INGRESO DE DATOS
# ==========================================
st.subheader("📝 Tabla de Tareas (Editable)")
st.info("Agrega, edita o elimina filas directamente en la tabla. Separa múltiples predecesores con comas (ej. 1, 2).")

# Datos por defecto orientados a una línea de proceso de envasado
datos_defecto = pd.DataFrame({
    "ID Tarea": ["1", "2", "3", "4", "5", "6", "7"],
    "Descripción": ["Preparación y limpieza", "Dosificado de producto", "Colocación de tapas", "Sellado neumático", "Etiquetado", "Inspección visual", "Empacado final"],
    "Duración (min)": [3, 7, 3, 2, 4, 2, 5],
    "Predecesores": ["", "1", "2", "2", "4", "3, 5", "6"]
})

# Editor de datos interactivo
df_tareas = st.data_editor(
    datos_defecto,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True
)

# ==========================================
# MOTOR DEL ALGORITMO RPP
# ==========================================
if st.button("🚀 Calcular Balanceo RPP", type="primary"):
    try:
        # 1. Procesamiento de datos y Predecesores
        df_tareas['ID Tarea'] = df_tareas['ID Tarea'].astype(str)
        tareas = df_tareas['ID Tarea'].tolist()
        duraciones = {str(row['ID Tarea']): row['Duración (min)'] for _, row in df_tareas.iterrows()}
        descripciones = {str(row['ID Tarea']): row['Descripción'] for _, row in df_tareas.iterrows()}
        
        predecesores = {}
        for _, row in df_tareas.iterrows():
            t = str(row['ID Tarea'])
            preds_raw = str(row['Predecesores']).replace(' ', '')
            if preds_raw in ['', 'nan', 'None', '-']:
                predecesores[t] = []
            else:
                preds_list = preds_raw.replace(';', ',').split(',')
                predecesores[t] = [p for p in preds_list if p in tareas]

        # 2. Dibujar Diagrama de Precedencias
        st.subheader("🕸️ Diagrama de Precedencias")
        dot = graphviz.Digraph(engine='dot')
        dot.attr(rankdir='LR', size='10,5')
        dot.attr('node', shape='circle', style='filled', color='#1f77b4', fontcolor='white', fontname='Helvetica')
        dot.attr('edge', color='#7f8c8d', penwidth='2.0', arrowsize='0.8')

        for t in tareas:
            dot.node(t, f"Tarea {t}\n({duraciones[t]} min)")
        for t, preds in predecesores.items():
            for p in preds:
                dot.edge(p, t)
        st.graphviz_chart(dot)

        # 3. Calcular Sucesores y Peso Posicional (RPi)
        sucesores = {t: [] for t in tareas}
        for t, preds in predecesores.items():
            for p in preds:
                sucesores[p].append(t)
                
        todos_sucesores = {}
        for t in tareas:
            visitados = set()
            stack = [t]
            while stack:
                curr = stack.pop()
                for succ in sucesores[curr]:
                    if succ not in visitados:
                        visitados.add(succ)
                        stack.append(succ)
            todos_sucesores[t] = visitados

        rpi = {t: duraciones[t] + sum(duraciones[s] for s in todos_sucesores[t]) for t in tareas}

        # 4. Reglas de Desempate y Ordenamiento (RPi, Duración, ID)
        def sorting_key(x):
            try: id_num = -int(x)
            except ValueError: id_num = x
            return (rpi[x], duraciones[x], id_num)

        tareas_ordenadas = sorted(tareas, key=sorting_key, reverse=True)

        # 5. Asignación a Estaciones de Trabajo
        estaciones = []
        estacion_actual = []
        tiempo_estacion_actual = 0
        tareas_asignadas = set()

        while len(tareas_asignadas) < len(tareas):
            asignacion_hecha = False
            for t in tareas_ordenadas:
                if t not in tareas_asignadas:
                    preds_cumplidos = all(p in tareas_asignadas for p in predecesores[t])
                    if preds_cumplidos and (tiempo_estacion_actual + duraciones[t] <= tiempo_ciclo):
                        estacion_actual.append(t)
                        tareas_asignadas.add(t)
                        tiempo_estacion_actual += duraciones[t]
                        asignacion_hecha = True
                        break # Volver a buscar desde la tarea de mayor RPi
                        
            if not asignacion_hecha:
                if estacion_actual:
                    estaciones.append({"tareas": estacion_actual, "tiempo": tiempo_estacion_actual})
                estacion_actual = []
                tiempo_estacion_actual = 0
                
        if estacion_actual:
            estaciones.append({"tareas": estacion_actual, "tiempo": tiempo_estacion_actual})

        # 6. Mostrar Resultados Finales
        st.subheader("✅ Resultados del Balanceo RPP")
        
        col1, col2, col3 = st.columns(3)
        num_estaciones = len(estaciones)
        tiempo_total_tareas = sum(duraciones.values())
        eficiencia = (tiempo_total_tareas / (num_estaciones * tiempo_ciclo)) * 100 if num_estaciones > 0 else 0
        
        col1.metric("Número de Estaciones", num_estaciones)
        col2.metric("Eficiencia de Línea", f"{eficiencia:.1f}%")
        col3.metric("Tiempo Ocioso Total", f"{(num_estaciones * tiempo_ciclo) - tiempo_total_tareas:.2f} min")

        # Preparar tabla de salida
        resultados_data = []
        for i, est in enumerate(estaciones):
            t_ocioso = tiempo_ciclo - est['tiempo']
            tareas_str = " → ".join(est['tareas'])
            resultados_data.append([f"Estación {i+1}", tareas_str, est['tiempo'], f"{t_ocioso:.2f}"])
            
        df_resultados = pd.DataFrame(resultados_data, columns=["Estación", "Secuencia de Tareas", "Tiempo Utilizado (min)", "Tiempo Ocioso (min)"])
        st.table(df_resultados)

        # Mostrar desglose de RPi
        with st.expander("Ver cálculos detallados de RP(i)"):
            df_rpi = pd.DataFrame({
                "Tarea": tareas_ordenadas,
                "Duración": [duraciones[t] for t in tareas_ordenadas],
                "Sucesores": [", ".join(todos_sucesores[t]) for t in tareas_ordenadas],
                "RP(i) Calculado": [rpi[t] for t in tareas_ordenadas]
            })
            st.dataframe(df_rpi, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Ocurrió un error en el cálculo. Verifica que el Tiempo de Ciclo no sea menor a la duración individual de ninguna tarea y que los predecesores estén bien escritos. (Error interno: {e})")