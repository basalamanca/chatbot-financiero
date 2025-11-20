import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Analista de Crédito IA", page_icon="💰", layout="wide")

# Título y descripción
st.title("🏦 Analista de Riesgo Financiero IA")
st.markdown("""
Esta herramienta analiza Estados Financieros en PDF utilizando Inteligencia Artificial.
**Instrucciones:**
1. Ingresa la Llave de API en el menú izquierdo.
2. Sube uno o varios PDFs (Estados de Situación Financiera y Resultados).
3. Haz clic en 'Analizar'.
""")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("🔐 Configuración")
    # Campo para que el comercial ponga la llave (o tú se la des)
    api_key = st.text_input("Ingresa la Google API Key", type="password")
    
    st.divider()
    st.info("El sistema acepta archivos con cualquier nombre y múltiples documentos al tiempo.")

# --- LÓGICA PRINCIPAL ---
if api_key:
    try:
        genai.configure(api_key=api_key)
        # Usamos el modelo que te funcionó
        model = genai.GenerativeModel('gemini-2.0-flash-001')
    except Exception as e:
        st.error(f"Error en la API Key: {e}")

    # --- SUBIDA DE ARCHIVOS ---
    uploaded_files = st.file_uploader(
        "📂 Sube los Estados Financieros (PDF)", 
        type=["pdf"], 
        accept_multiple_files=True
    )

    # Botón de Análisis
    if st.button("🚀 Analizar Documentos", type="primary", disabled=not uploaded_files):
        
        if not uploaded_files:
            st.warning("Por favor sube al menos un archivo.")
        else:
            # BARRA DE PROGRESO
            progress_text = "Iniciando operación..."
            my_bar = st.progress(0, text=progress_text)
            
            gemini_files = []
            temp_paths = []

            try:
                # 1. PROCESAR ARCHIVOS (Sin importar el nombre)
                for i, uploaded_file in enumerate(uploaded_files):
                    my_bar.progress((i + 1) / len(uploaded_files) * 0.3, text=f"Subiendo {uploaded_file.name}...")
                    
                    # Crear archivo temporal para enviarlo a Google
                    # (Esto soluciona el problema de los nombres)
                    suffix = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                        temp_paths.append(tmp_path)

                    # Subir a la nube de Gemini
                    g_file = genai.upload_file(path=tmp_path, display_name=uploaded_file.name)
                    
                    # Esperar a que Google procese el archivo
                    while g_file.state.name == "PROCESSING":
                        time.sleep(1)
                        g_file = genai.get_file(g_file.name)
                    
                    gemini_files.append(g_file)

                my_bar.progress(0.5, text="🧠 Analizando datos financieros y calculando Score...")

                # 2. EL PROMPT MAESTRO (Tus reglas de negocio)
                prompt = """
                Actúa como un Vicepresidente de Riesgo de Crédito Senior.
                Analiza la información contenida en LOS DOCUMENTOS ADJUNTOS (unificados).

                Sigue ESTRICTAMENTE estas reglas de negocio para el informe:

                === 1. NORMALIZACIÓN DE PERIODOS ===
                - Si comparas un CORTE (ej. Junio) vs un AÑO COMPLETO (Dic):
                * Para Crecimiento en Ventas: Calcula el PROMEDIO MENSUAL de cada periodo y compara esos promedios.

                === 2. CÁLCULO DEL SCORE (VARIABLES 1 a 7 PUNTOS) ===
                Calcula cada indicador. Si cumple = 7 pts, Si no = 0 o 1 pt.

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
                11. Tamaño Empresa (Ventas Anuales):
                    - >10.000MM = 7 pts
                    - 3.000-10.000MM = 3 pts
                    - <3.000MM = 0 pts
                12. Capital de Trabajo (Positivo): SI=7 | NO=0

                --- PENALIZACIÓN ---
                13. Patrimonio Negativo: RESTA 14 PUNTOS a la suma total.

                >>> SCORE FINAL = (Suma puntos - Penalizaciones) / 12.

                === 3. SUGERENCIA DE LÍNEA (Orden de Prioridad) ===
                A. "FACTORING ENDOSO CON PAGADORES AAA": Si Score < 3 OR Margen Op Negativo OR Patrimonio Negativo OR Endeudamiento > 80%.
                B. "CONFIRMING": Si Score 6-7 AND Ventas > 30.000 Millones AND Todo OK. 
                * Nota obligatoria: "Sujeto a estudio de endosables como fuente de pago y calidad de clientes en facturacion".
                C. "FACTORING": Cualquier otro caso (Score 3-5.9 o Score alto con ventas bajas).

                === 4. CUPO SUGERIDO ===
                - Base: Ventas de UN MES (Promedio del último periodo disponible).
                - Si es Factoring Endoso AAA: 20% de un mes.
                - Si es Factoring/Confirming: 100% de un mes.
                - TOPE MÁXIMO: 5.000 Millones.
                - Si cupo > 500 Millones: Nota "Sujeto a castigo por sector".

                === SALIDA ===
                Genera un informe ejecutivo limpio en Markdown. Usa tablas si es necesario.
                Estructura:
                1. Detalle de Score (Lista punto por punto con valor real y puntaje asignado).
                2. Score Final y Nivel de Riesgo (Bajo/Medio/Alto).
                3. Estructuración (Línea Sugerida y Cupo en Millones).
                4. Alertas de Riesgo detectadas.
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
                # 5. LIMPIEZA DE ARCHIVOS (Importante para no llenar tu nube)
                for g_file in gemini_files:
                    try: g_file.delete()
                    except: pass
                for path in temp_paths:
                    try: os.unlink(path)
                    except: pass

else:
    st.warning("👈 Por favor ingresa tu API Key en la barra lateral para comenzar.")