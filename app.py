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
1. Puedes cargar un solo archivo o varios (ej: un PDF con el corte reciente y otro con el cierre anterior).
2. El sistema buscará automáticamente los dos periodos más recientes para comparar.
3. Haz clic en **"Analizar Documentos"**.
""")

# --- CONFIGURACIÓN DE API (LLAVE FIJA) ---
api_key = "AIzaSyA4CBrLnh85FHGyMptRimalbMSSCMQqtbc"

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-001')
except Exception as e:
    st.error(f"Error en la configuración de API: {str(e)}")

# --- FUNCIÓN PRINCIPAL DE ANÁLISIS ---
def analizar_documentos(uploaded_files):
    gemini_files = []
    temp_paths = []
    
    status_text = st.empty()
    progress_bar = st.progress(0)

    try:
        # 1. PROCESAR Y SUBIR CADA ARCHIVO
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"📤 Subiendo archivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}...")
            
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
                temp_paths.append(tmp_path)

            g_file = genai.upload_file(path=tmp_path, display_name=uploaded_file.name)
            
            while g_file.state.name == "PROCESSING":
                time.sleep(1)
                g_file = genai.get_file(g_file.name)
            
            if g_file.state.name == "FAILED":
                st.error(f"Falló la lectura del archivo: {uploaded_file.name}")
                return None

            gemini_files.append(g_file)
            progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)

        status_text.text("🧠 Cruzando información de los documentos y aplicando reglas...")
        progress_bar.progress(0.75)

        # 2. PROMPT MAESTRO (ACTUALIZADO CON TUS PARÁMETROS)
        prompt = """
        Actúa como un Vicepresidente de Riesgo de Crédito Senior.
        Analiza la información contenida en TODOS LOS DOCUMENTOS ADJUNTOS.

        === INSTRUCCIÓN CRÍTICA DE SELECCIÓN DE DATOS ===
        Tienes acceso a uno o varios documentos. Tu primera tarea es identificar las fechas de corte de todos los estados financieros encontrados.
        1. Ordena las fechas cronológicamente.
        2. Selecciona ÚNICAMENTE los dos periodos más recientes para hacer el análisis comparativo (Periodo Actual vs Periodo Anterior).
        3. Ignora periodos más antiguos si existen más de dos.

        Sigue ESTRICTAMENTE las siguientes reglas de negocio parametrizadas:

        === 1. NORMALIZACIÓN DE PERIODOS ===
        - Si comparas un periodo de CORTE (ej. Junio) vs un AÑO COMPLETO (Dic):
          * Para calcular el Crecimiento en Ventas, calcula el PROMEDIO DE VENTAS MENSUAL de cada periodo y compara esos promedios.
          * (Ej: Ventas Junio / 6 vs Ventas Año Anterior / 12).

        === 2. CÁLCULO DEL SCORE (VARIABLES 1 a 7 PUNTOS) ===
        Calcula cada indicador. Asigna 7 puntos si cumple la regla (EXITOSO) o 0/1 según se indique si falla.

        1. Crecimiento en Ventas:
           - Regla: ¿El crecimiento es mayor a la inflación del último año (usa 10% si no hay dato)?
           - Puntos: SI = 7 | NO = 0
        2. Crecimiento Real (Margen Bruto):
           - Regla: ¿El margen bruto % es igual o mayor al del año anterior?
           - Puntos: SI = 7 | NO = 1
        3. Margen Operacional:
           - Regla: ¿Es positivo (>0)?
           - Puntos: SI = 7 | NO = 0
        4. Endeudamiento (Pasivo Total / Activo Total):
           - Regla: ¿Es saludable (< 75%)?
           - Puntos: SI = 7 | NO = 0
        5. Razón Corriente:
           - Regla: ¿Es mayor a 0.9?
           - Puntos: SI = 7 | NO = 0
        6. Capital Pagado:
           - Regla: ¿Es mayor al 10% del Patrimonio Total?
           - Puntos: SI = 7 | NO = 0
        7. Utilidad Acumulada:
           - Regla: ¿Es positiva?
           - Puntos: SI = 7 | NO = 0
        8. Rotación CXC (Cartera):
           - Regla: ¿Días CXC son menores o iguales a 90 días?
           - Puntos: SI = 7 | NO = 0
        9. Rotación CXP (Proveedores):
           - Regla: ¿Días CXP son menores o iguales a 120 días?
           - Puntos: SI = 7 | NO = 0
        10. Relación de Rotaciones:
            - Regla: ¿Días CXC > Días CXP? (Interpreta literalmente la regla de parámetros: Si rotación cobro > rotación pago).
            - Puntos: SI = 7 | NO = 0
        11. Tamaño Empresa (Ventas Anuales):
            - > 10.000 Millones = 7 puntos
            - 3.000 a 10.000 Millones = 3 puntos
            - < 3.000 Millones = 0 puntos
        12. Capital de Trabajo:
            - Regla: ¿Es positivo?
            - Puntos: SI = 7 | NO = 0

        --- PENALIZACIÓN ---
        13. Patrimonio Negativo:
            - Si el patrimonio es negativo, RESTA 14 PUNTOS a la suma total de los puntos anteriores.

        >>> SCORE FINAL = (Suma de puntos - Penalizaciones) / 12 (o el número de variables evaluadas).

        === 3. MATRIZ DE RIESGO ===
        - Score 6.0 - 7.0: RIESGO BAJO (Cliente AAA)
        - Score 4.0 - 5.9: RIESGO MEDIO (Cliente AA)
        - Score 1.0 - 3.9: RIESGO ALTO (Cliente B/C)

        === 4. SUGERENCIA DE LÍNEA (Prioridad Estricta) ===
        A. "FACTORING ENDOSO CON PAGADORES AAA":
           - Sugerir SI: Score < 3 OR Margen Operacional Negativo OR Patrimonio Negativo OR Endeudamiento > 80%.
        
        B. "CONFIRMING":
           - Sugerir SI: Score entre 6 y 7 AND Ventas Anuales >= 30.000 Millones AND Cliente OK en todo.
           - NOTA OBLIGATORIA: "Sujeto a estudio de endosables como fuente de pago y calidad de clientes en facturacion".
        
        C. "FACTORING":
           - Sugerir en cualquier otro caso (Score 3-5.9, o Score alto con ventas < 30.000MM).

        === 5. CUPO SUGERIDO (En Millones COP) ===
        - Base: Promedio de ventas de UN MES.
        - Reglas:
          * Si es Factoring Endoso AAA: Cupo = 20% de un mes.
          * Si es Factoring: Cupo = 100% de un mes.
          * Si es Confirming: Cupo = 100% de un mes CASTIGADO al 70% (Es decir, Base * 0.70).
        - TOPE MÁXIMO GLOBAL: 5.000 Millones.
        - CASTIGO SECTORIAL: Si el cupo calculado > 500 Millones, agregar nota: "Sujeto a castigo por sector según tabla".

        === 6. ALERTAS (Si aplican) ===
        - Patrimonio Negativo -> "Alerta: Posible reorganización o insolvencia".
        - Rotación CXC < Rotación CXP -> "Alerta: Cliente con falta evidente de caja".
        - Caída ventas o Margen se vuelve negativo -> "Alerta: Problemas en la operación".
        - Margen Bruto negativo -> "Alerta: Fallas en gestión o mercado".

        === SALIDA EN MARKDOWN ===
        Genera un informe limpio.
        1. **Resumen de Periodos Analizados:** Indica claramente qué fechas se compararon.
        2. **Detalle del Score:** Tabla con Indicador | Valor Real | Puntos.
        3. **Resultado Final:** Score y Nivel de Riesgo.
        4. **Estructuración:** Línea Sugerida y Cupo Sugerido.
        5. **Alertas:** Lista de alertas.
        """

        # 3. ENVIAR A GEMINI
        request_content = [prompt] + gemini_files
        response = model.generate_content(request_content)
        
        my_bar.progress(1.0, text="¡Análisis completado!")
        time.sleep(0.5)
        my_bar.empty()

        # 4. MOSTRAR RESULTADO
        st.success("✅ Análisis generado exitosamente")
        st.markdown("---")
        st.markdown(response.text)

    except Exception as e:
        st.error(f"❌ Ocurrió un error: {str(e)}")
    
    finally:
        # 5. LIMPIEZA
        for g_file in gemini_files:
            try: g_file.delete()
            except: pass
        for path in temp_paths:
            try: os.unlink(path)
            except: pass

# --- INTERFAZ DE USUARIO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.info("Sube aquí los archivos PDF (Comparativos o Separados).")
    uploaded_files = st.file_uploader("Cargar PDFs", type=["pdf"], accept_multiple_files=True)
    
    analyze_btn = st.button("🔍 Analizar Documentos", type="primary", disabled=not uploaded_files)

with col2:
    if analyze_btn and uploaded_files:
        analizar_documentos(uploaded_files)
    elif not uploaded_files:
        st.warning("👈 Sube al menos un archivo PDF para ver el análisis aquí.")