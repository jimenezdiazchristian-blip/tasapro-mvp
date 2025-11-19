import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="TasaPro Oficial", page_icon="⚖️", layout="wide")

# --- FUNCIÓN DE CONEXIÓN REAL CON CATASTRO (OVC) ---
def consultar_catastro_real(rc):
    """
    Conecta con la Sede Electrónica del Catastro (España)
    y devuelve los datos del inmueble a partir de la Referencia Catastral.
    """
    # URL Oficial del servicio de consulta por RC
    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # Parsear el XML
            root = ET.fromstring(response.content)
            
            # Buscar errores de catastro
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": err.text}

            # Extraer Dirección
            calle = root.find(".//domicilio/tv").text + " " + root.find(".//domicilio/nv").text
            numero = root.find(".//domicilio/pnp").text if root.find(".//domicilio/pnp") is not None else ""
            municipio = root.find(".//muni/nm").text
            provincia = root.find(".//prov/np").text
            direccion_completa = f"{calle}, {numero}, {municipio} ({provincia})"
            
            # Extraer Datos Físicos (Superficie y Antigüedad)
            # Nota: Catastro devuelve una lista de construcciones, sumamos o cogemos la principal
            superficie = 0
            ano_construccion = 0
            
            # Buscamos el nodo de bienes inmuebles
            bico = root.find(".//bico/bi/de/superficie") # Simplificación para MVP
            
            # Intentamos sacar la superficie construida total
            try:
                # Buscar superficie en datos economicos (bi/de)
                sup_elem = root.find(".//bico/bi/de/supc")
                if sup_elem is not None:
                    superficie = int(sup_elem.text)
                
                # Buscar año antigüedad
                ant_elem = root.find(".//bico/bi/de/ant")
                if ant_elem is not None:
                    ano_construccion = int(ant_elem.text)
            except:
                pass # Si falla el parseo específico, dejamos 0 para que lo rellene el usuario

            uso = root.find(".//bico/bi/de/uso").text if root.find(".//bico/bi/de/uso") is not None else "Residencial"

            return {
                "exito": True,
                "direccion": direccion_completa,
                "superficie": superficie,
                "ano": ano_construccion,
                "uso": uso
            }
        else:
            return {"error": "Error de conexión con Catastro"}
    except Exception as e:
        return {"error": f"Excepción técnica: {str(e)}"}

# --- CLASE PDF CON DISEÑO JURÍDICO ---
class InformePDF(FPDF):
    def header(self):
        # Logo Empresa (Izquierda)
        if 'logo' in st.session_state and st.session_state.logo:
             # Guardar temporalmente
            img = Image.open(st.session_state.logo)
            # Convertir a RGB si es RGBA para evitar error de FPDF
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save("temp_logo_print.jpg")
            self.image("temp_logo_print.jpg", 15, 10, 30)
        
        # Título Corporativo (Derecha)
        self.set_font('Times', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'INFORME TÉCNICO DE VALORACIÓN', 0, 1, 'R')
        self.set_font('Times', '', 8)
        self.cell(0, 5, 'Conforme a Orden ECO/805/2003', 0, 1, 'R')
        
        # Línea separadora
        self.set_draw_color(26, 58, 89) # Azul oscuro corporativo
        self.set_line_width(0.5)
        self.line(15, 30, 195, 30)
        self.ln(25)

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(200, 200, 200)
        self.line(15, 275, 195, 275)
        
        self.set_font('Arial', '', 7)
        self.set_text_color(128, 128, 128)
        self.multi_cell(0, 3, 'DOCUMENTO CONFIDENCIAL. Este informe contiene datos de carácter personal protegidos por la Ley Orgánica 3/2018 de Protección de Datos. Su uso queda restringido a la finalidad expresada en el mismo.', 0, 'C')
        
        self.set_y(-10)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} | Ref. Exp: {st.session_state.get("ref_expediente", "S/N")}', 0, 0, 'R')

    def titulo_seccion(self, titulo):
        self.set_font('Arial', 'B', 11)
        self.set_fill_color(240, 240, 245) # Gris azulado muy suave
        self.set_text_color(26, 58, 89)
        self.cell(0, 8, f"  {titulo.upper()}", 0, 1, 'L', 1)
        self.ln(4)

    def campo_dato(self, etiqueta, valor):
        self.set_font('Arial', 'B', 9)
        self.set_text_color(50, 50, 50)
        self.cell(50, 6, etiqueta, 0, 0)
        self.set_font('Arial', '', 9)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, str(valor), 0, 1)

def generar_pdf_juridico(datos):
    pdf = InformePDF()
    pdf.add_page()
    
    # 1. IDENTIFICACIÓN DEL INFORME
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'CERTIFICADO DE TASACIÓN INMOBILIARIA', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.titulo_seccion("1. IDENTIFICACIÓN DE LOS INTERVINIENTES")
    pdf.campo_dato("Sociedad/Técnico Tasador:", datos['tasador'])
    pdf.campo_dato("Nº de Colegiado/Registro:", datos['colegiado'])
    pdf.campo_dato("Solicitante del informe:", datos['cliente'])
    pdf.campo_dato("Finalidad de la valoración:", datos['finalidad'])
    pdf.ln(5)

    pdf.titulo_seccion("2. IDENTIFICACIÓN FÍSICA Y REGISTRAL")
    pdf.campo_dato("Dirección del Inmueble:", datos['direccion'])
    pdf.campo_dato("Referencia Catastral:", datos['ref_catastral'])
    pdf.campo_dato("Municipio / Provincia:", "Según Catastro") # Simplificado para demo
    
    # Cuadro de superficies con bordes
    pdf.ln(2)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(180, 180, 180)
    pdf.cell(60, 7, "Superficie Construida", 1, 0, 'C', 1)
    pdf.cell(60, 7, "Año Construcción", 1, 0, 'C', 1)
    pdf.cell(60, 7, "Estado de Conservación", 1, 1, 'C', 1)
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 8, f"{datos['superficie']} m2", 1, 0, 'C')
    pdf.cell(60, 8, f"{datos['antiguedad']}", 1, 0, 'C')
    pdf.cell(60, 8, datos['estado'], 1, 1, 'C')
    pdf.ln(8)

    pdf.titulo_seccion("3. ANÁLISIS DE MERCADO Y CÁLCULO")
    pdf.set_font('Arial', '', 9)
    texto_mercado = f"Se ha realizado un estudio de mercado en el entorno próximo al inmueble, localizando testigos comparables con características similares en cuanto a tipología, antigüedad y ubicación. El valor unitario medio de la zona se sitúa en {datos['precio_m2_zona']} EUR/m2."
    pdf.multi_cell(0, 5, texto_mercado)
    pdf.ln(3)
    pdf.campo_dato("Metodología aplicada:", "Método de Comparación (Art. 21 Orden ECO/805/2003)")
    pdf.ln(5)

    # 4. VALORACIÓN FINAL (DESTACADO)
    pdf.ln(5)
    pdf.set_draw_color(26, 58, 89)
    pdf.set_line_width(0.8)
    pdf.rect(35, pdf.get_y(), 140, 35) # Cuadro borde grueso
    
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 6, "VALOR DE TASACIÓN CERTIFICADO", 0, 1, 'C')
    
    pdf.set_font('Arial', 'B', 22)
    pdf.set_text_color(26, 58, 89)
    pdf.cell(0, 12, f"{datos['valor_final']} EUR", 0, 1, 'C')
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, f"Fecha de emisión: {datetime.date.today().strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(15)

    # 5. CERTIFICACIÓN Y FIRMA
    pdf.titulo_seccion("4. DECLARACIÓN Y FIRMA")
    pdf.set_font('Arial', '', 9)
    declaracion = "El técnico abajo firmante CERTIFICA que ha realizado la visita de inspección ocular al inmueble objeto de valoración, comprobando sus características físicas y aparentes, y que el presente informe ha sido elaborado con imparcialidad y conforme a la normativa vigente."
    pdf.multi_cell(0, 5, declaracion)
    pdf.ln(15)
    
    # Espacio firma
    pdf.cell(90, 0, "", 0, 0)
    pdf.cell(60, 0, "Fdo: El Técnico Tasador", 0, 1, 'C')
    pdf.cell(90, 0, "", 0, 0) # Espacio para firma digital
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ APP ---
with st.sidebar:
    st.header("🏛️ TasaPro Oficial")
    logo_file = st.file_uploader("Logo Corporativo", type=['jpg','png'])
    if logo_file:
        st.session_state.logo = logo_file
        st.image(logo_file, width=150)
    
    st.markdown("### Datos del Técnico")
    tasador = st.text_input("Nombre Completo", "Juan Pérez García")
    colegiado = st.text_input("Nº Colegiado / DNI", "28.333-Arq")
    st.session_state.ref_expediente = st.text_input("Ref. Expediente", "EXP-2024-089")

st.title("Emisión de Informe de Valoración")
st.info("Sistema conectado a Sede Electrónica del Catastro (OVC)")

# Bloque 1: Conexión Catastro
col_search, col_result = st.columns([1, 2])
with col_search:
    st.subheader("1. Importar Datos")
    rc_input = st.text_input("Referencia Catastral (20 caracteres)", max_chars=20)
    buscar = st.button("📡 Buscar en Catastro")

# Variables de estado para guardar los datos de catastro
if 'catastro_data' not in st.session_state:
    st.session_state.catastro_data = {"dir": "", "sup": 0, "ano": 1990}

if buscar and rc_input:
    with st.spinner("Conectando con Sede Electrónica..."):
        datos_ovc = consultar_catastro_real(rc_input)
        if "error" in datos_ovc:
            st.error(f"Error: {datos_ovc['error']}")
        else:
            st.success("¡Datos oficiales recuperados!")
            st.session_state.catastro_data = {
                "dir": datos_ovc['direccion'],
                "sup": datos_ovc['superficie'],
                "ano": datos_ovc['ano']
            }

# Bloque 2: Formulario (Se rellena solo)
with st.form("formulario_informe"):
    st.subheader("2. Datos del Inmueble")
    col1, col2 = st.columns(2)
    
    direccion = col1.text_input("Dirección", value=st.session_state.catastro_data["dir"])
    cliente = col2.text_input("Solicitante / Cliente")
    
    c1, c2, c3 = st.columns(3)
    superficie = c1.number_input("Superficie (m2)", value=st.session_state.catastro_data["sup"])
    antiguedad = c2.number_input("Año Construcción", value=st.session_state.catastro_data["ano"])
    estado = c3.selectbox("Estado", ["Reformado", "Buen estado", "A reformar", "Origen"])
    
    st.subheader("3. Valoración")
    finalidad = st.selectbox("Finalidad", ["Garantía Hipotecaria", "Asesoramiento Valor de Mercado", "Reparto Herencia"])
    
    vp1, vp2 = st.columns(2)
    precio_zona = vp1.number_input("Valor Medio Mercado (€/m2)", value=2100)
    coef = vp2.slider("Coeficiente Corrector (Vistas, altura...)", 0.8, 1.2, 1.0)
    
    valor_tasacion = superficie * precio_zona * coef
    st.markdown(f"### 💰 Valor Calculado: **{valor_tasacion:,.2f} €**")
    
    generar = st.form_submit_button("📄 GENERAR INFORME OFICIAL")

if generar:
    if not cliente or not rc_input:
        st.error("Faltan datos obligatorios (Cliente o Ref. Catastral)")
    else:
        datos_pdf = {
            "tasador": tasador,
            "colegiado": colegiado,
            "cliente": cliente,
            "direccion": direccion,
            "ref_catastral": rc_input,
            "superficie": superficie,
            "antiguedad": antiguedad,
            "estado": estado,
            "finalidad": finalidad,
            "precio_m2_zona": precio_zona,
            "valor_final": f"{valor_tasacion:,.2f}"
        }
        
        pdf_bytes = generar_pdf_juridico(datos_pdf)
        
        st.balloons()
        st.success("Informe oficial generado y firmado digitalmente (simulado).")
        st.download_button(
            "⬇️ Descargar PDF Jurídico",
            data=pdf_bytes,
            file_name=f"Informe_{rc_input}.pdf",
            mime="application/pdf"
        )