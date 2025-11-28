import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Analista Financiero IA", page_icon="📊", layout="wide")

st.title("🤖 Analista de Riesgo Financiero (Multi-Documento)")
st.markdown("""
Sube los Estados Financieros (PDF).
**Instrucciones:**
1. Puedes cargar un solo archivo o varios (comparativos).
2. El sistema detectará automáticamente la información.
3. Haz clic en **"Analizar Documentos"**.
""")

# --- CONFIGURACIÓN DE API (LLAVE FIJA) ---
api_key = "AIzaSyA4CBrLnh85FHGyMptRimalbMSSCMQqtbc"

try:
    genai.configure(api_key=api_key)
    # Usamos el modelo 2.0 Flash (el más eficiente para documentos)
    model = genai.GenerativeModel('gemini-2.0-flash-001')
except Exception as e:
    st.error(f"Error en la configuración de API: {str(e)}")

# --- FUNCIÓN PRINCIPAL DE ANÁLISIS ---
def analizar_documentos(uploaded_files):
    gemini_files = []
    temp_paths = []
    
    # Espacios para mostrar estado (DEFINICIÓN INICIAL)
    status_text = st.empty()
    progress_bar = st.progress(0)

    try:
        # 1. PROCESAR Y SUBIR CADA ARCHIVO
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"📤 Subiendo archivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}...")
            
            # Crear archivo temporal
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
                temp_paths.append(tmp_path)

            # Subir a Google Gemini
            g_file = genai.upload_file(path=tmp_path, display_name=uploaded_file.name)
            
            # Esperar procesamiento
            while g_file.state.name == "PROCESSING":
                time.sleep(1)
                g_file = genai.get_file(g_file.name)
            
            if g_file.state.name == "FAILED":
                st.error(f"Falló la lectura del archivo: {uploaded_file.name}")
                return None

            gemini_files.append(g_file)
            # Actualizar barra de progreso (usando el nombre correcto: progress_bar)
            progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)

        status_text.text("🧠 Analizando información cruzada y calculando Score...")
        progress_bar.progress(0.75)

        # 2. PROMPT MAESTRO (REGLAS DE NEGOCIO ROBUSTAS)
        prompt = """
        Actúa como un Vicepresidente de Riesgo de Crédito Senior.
        Analiza la información contenida en LOS DOCUMENTOS ADJUNTOS.
        
        Tu trabajo es UNIFICAR la información, identificar las fechas de corte de cada documento y realizar el análisis comparativo.

        Sigue ESTRICTAMENTE estas reglas de negocio para el informe:

        === 1. NORMALIZACIÓN DE PERIODOS ===
        - Identifica las fechas de los documentos.
        - Si comparas un CORTE (ej. Junio) vs un AÑO COMPLETO (Dic):
          * Para Crecimiento en Ventas: Calcula el PROMEDIO MENSUAL de cada periodo y compara esos promedios.

        === 2. CÁLCULO DEL SCORE (VARIABLES 1 a 7 PUNTOS) ===
        Calcula cada indicador. Si cumple = 7 pts, Si no = 0 o 1 pt (según se indique).

        1. Crecimiento Ventas (>Inflación/10%): SI=7 | NO=0
        2. Crecimiento Margen Bruto (>= año anterior): SI=7 | NO=1
        3. Margen Operacional (Positivo): SI=7 | NO=0
        4. Endeudamiento (Saludable <70%): SI=7 | NO=0
        5. Razón Corriente (>0.9): SI=7 | NO=0
        6. Capital Pagado (>10% del Patrimonio): SI=7 | NO=0
        7. Utilidad Acumulada (Positiva): SI=7 | NO=0
        8. Rotación CXC (<=90 días): SI=7 | NO=0
        9. Rotación CXP (<=120 días): SI=7 | NO=0
        10. Relación Rotaciones (Días CXC > Días CXP): SI=7 | NO=0
        11. Tamaño Empresa (Ventas Anuales Proyectadas):
            - >10.000MM = 7 pts
            - 3.000-10.000MM = 3 pts
            - <3.000MM = 0 pts
        12. Capital de Trabajo (Positivo): SI=7 | NO=0

        --- PENALIZACIÓN ---
        13. Patrimonio Negativo: Si existe, RESTA 14 PUNTOS a la suma total de puntos antes de promediar.

        >>> CÁLCULO SCORE FINAL = (Suma de puntos - Penalizaciones) / 12.

        === 3. SUGERENCIA DE LÍNEA (Orden de Prioridad) ===
        A. "FACTORING ENDOSO CON PAGADORES AAA": 
           - Sugerir SI: Score < 3 OR Margen Op Negativo OR Patrimonio Negativo OR Endeudamiento > 80%.
        
        B. "CONFIRMING": 
           - Sugerir SI: Score entre 6 y 7 AND Ventas Anuales > 30.000 Millones AND No tiene causales de línea A.
           - NOTA OBLIGATORIA: "Sujeto a estudio de endosables como fuente de pago y calidad de clientes en facturacion".
        
        C. "FACTORING": 
           - Sugerir en cualquier otro caso (ej: Score 3-5.9, o Score alto con ventas bajas).

        === 4. CUPO SUGERIDO ===
        - Base de cálculo: Ventas de UN MES (Promedio del último periodo disponible).
        - Si la línea es Factoring Endoso AAA: Cupo = 20% de un mes.
        - Si la línea es Factoring/Confirming: Cupo = 100% de un mes.
        - TOPE MÁXIMO GLOBAL: 5.000 Millones de pesos. (Si el cálculo da más, ajusta a 5.000).
        - Si cupo > 500 Millones: Agregar nota "Sujeto a castigo por sector según tabla".

        === SALIDA ===
        Genera un informe ejecutivo limpio en formato Markdown.
        Estructura requerida:
        1. **Detalle del Score:** Lista los 12 indicadores, mostrando el Valor Real calculado y los Puntos asignados. Muestra la penalización si aplica.
        2. **Resultados Finales:** Score Final (1 decimal) y Nivel de Riesgo (Bajo/Medio/Alto).
        3. **Estructuración:** Línea Sugerida (con notas si aplican) y Cupo Sugerido (Valor en millones COP).
        4. **Alertas:** Lista de alertas detectadas (Patrimonio negativo, iliquidez, etc).
        """

        # 3. ENVIAR A GEMINI
        request_content = [prompt] + gemini_files
        response = model.generate_content(request_content)
        
        # --- AQUÍ ESTABA EL ERROR ANTERIOR (CORREGIDO: usamos progress_bar) ---
        progress_bar.progress(1.0, text="¡Análisis completado!")
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()

        # 4. MOSTRAR RESULTADO (Y retornarlo para confirmación)
        st.success("✅ Análisis generado exitosamente")
        st.markdown("---")
        st.markdown(response.text)
        
        return response.text

    except Exception as e:
        st.error(f"❌ Ocurrió un error: {str(e)}")
        return None
    
    finally:
        # 5. LIMPIEZA DE ARCHIVOS
        for g_file in gemini_files:
            try: g_file.delete()
            except: pass
        for path in temp_paths:
            try: os.unlink(path)
            except: pass

# --- INTERFAZ DE USUARIO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.info("Sube aquí los archivos PDF (Balance, Estado de Resultados, Comparativos).")
    uploaded_files = st.file_uploader("Cargar PDFs", type=["pdf"], accept_multiple_files=True)
    
    analyze_btn = st.button("🔍 Analizar Documentos", type="primary", disabled=not uploaded_files)

with col2:
    if analyze_btn and uploaded_files:
        analizar_documentos(uploaded_files)
    elif not uploaded_files:
        st.warning("👈 Sube al menos un archivo PDF para ver el análisis aquí.")