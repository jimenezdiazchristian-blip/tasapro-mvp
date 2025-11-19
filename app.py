import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import os
import tempfile

# --- 1. CONFIGURACIÓN Y ESTÉTICA (CSS PRO) ---
st.set_page_config(page_title="TasaPro España", page_icon="🏢", layout="wide")

# Inyección de CSS personalizado para diseño profesional
st.markdown("""
    <style>
    /* Importar fuente moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Fondo general suave */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Estilo de la Barra Lateral */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
        box-shadow: 2px 0 5px rgba(0,0,0,0.02);
    }

    /* Encabezados */
    h1 {
        color: #0F172A;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    h2, h3 {
        color: #334155;
        font-weight: 600;
    }

    /* Inputs y Selectboxes */
    .stTextInput > div > div > input, 
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        color: #334155;
    }
    .stTextInput > div > div > input:focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 2px rgba(37,99,235,0.2);
    }

    /* Botón Principal (Generar) */
    .stButton > button {
        background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%);
        color: white;
        border: none;
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 6px -1px rgba(30, 58, 138, 0.2);
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 8px -1px rgba(30, 58, 138, 0.3);
        background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%);
    }

    /* Botón Secundario (Buscar Catastro) */
    div[data-testid="column"] button {
        background: #F1F5F9;
        color: #0F172A;
        border: 1px solid #CBD5E1;
    }
    div[data-testid="column"] button:hover {
        background: #E2E8F0;
        color: #1E3A8A;
    }

    /* Tarjeta de Resultado (Valor de Tasación) */
    div[data-testid="metric-container"] {
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 15px;
        border-radius: 10px;
        color: #172554;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    label[data-testid="stMetricLabel"] {
        color: #1E40AF !important;
        font-size: 0.9rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #1E3A8A !important;
        font-weight: 700 !important;
    }

    /* Alertas y mensajes */
    .stAlert {
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LÓGICA (INTACTA) ---

# --- FUNCIÓN CONEXIÓN CATASTRO ---
def get_xml_text(root, paths, default=""):
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        element = root.find(path)
        if element is not None and element.text:
            return element.text
    return default

def consultar_catastro_real(rc_input):
    # Limpieza agresiva
    rc = str(rc_input).replace(" ", "").replace("\t", "").replace("\n", "").replace("-", "").replace(".", "").upper()
    
    if len(rc) != 20:
        return {"error": f"Longitud incorrecta: {len(rc)} caracteres. Deben ser 20 exactos."}

    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            xml_text = response.text.replace('xmlns="http://www.catastro.meh.es/"', '').replace('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', '')
            root = ET.fromstring(xml_text)
            
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": f"Catastro rechaza la referencia: {err.text}"}

            tv = get_xml_text(root, [".//ldt/dom/tv", ".//domicilio/tv", ".//tv"], "")
            nv = get_xml_text(root, [".//ldt/dom/nv", ".//domicilio/nv", ".//nv"], "")
            calle = f"{tv} {nv}".strip()
            numero = get_xml_text(root, [".//ldt/dom/pnp", ".//domicilio/pnp", ".//pnp"], "")
            municipio = get_xml_text(root, [".//dt/nm", ".//muni/nm", ".//nm"], "")
            provincia = get_xml_text(root, [".//dt/np", ".//prov/np", ".//np"], "")
            
            if not calle and not municipio:
                direccion_completa = "Dirección no detallada en Sede (Rellenar manual)"
            else:
                direccion_completa = f"{calle}, {numero}, {municipio} ({provincia})"
            
            superficie = 0
            ano_construccion = 1990
            try:
                sup_txt = get_xml_text(root, [".//bico/bi/de/supc", ".//de/supc"])
                if sup_txt: superficie = int(sup_txt)
                ant_txt = get_xml_text(root, [".//bico/bi/de/ant", ".//de/ant"])
                if ant_txt: ano_construccion = int(ant_txt)
            except: pass 

            return {
                "exito": True, "direccion": direccion_completa,
                "superficie": superficie, "ano": ano_construccion,
                "uso": get_xml_text(root, [".//bico/bi/de/uso", ".//de/uso"], "Residencial")
            }
        return {"error": "Error de conexión con servidor Catastro"}
    except Exception as e:
        return {"error": f"Error técnico: {str(e)}"}

# --- CLASE PDF ---
class InformePDF(FPDF):
    def header(self):
        if 'logo' in st.session_state and st.session_state.logo:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                    tmp_logo.write(st.session_state.logo.getvalue())
                    tmp_logo_path = tmp_logo.name
                self.image(tmp_logo_path, 15, 10, 30)
            except: pass
        self.set_font('Times', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'INFORME TÉCNICO DE VALORACIÓN', 0, 1, 'R')
        self.set_font('Times', '', 8)
        self.cell(0, 5, 'Orden ECO/805/2003', 0, 1, 'R')
        self.set_draw_color(26, 58, 89)
        self.line(15, 30, 195, 30)
        self.ln(25)

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(200, 200, 200)
        self.line(15, 275, 195, 275)
        self.set_font('Arial', '', 7)
        self.set_text_color(128, 128, 128)
        self.multi_cell(0, 3, 'DOCUMENTO CONFIDENCIAL. Uso restringido.', 0, 'C')
        self.set_y(-10)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

    def titulo_seccion(self, titulo):
        self.set_font('Arial', 'B', 11)
        self.set_fill_color(240, 240, 245)
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

def generar_pdf_completo(datos, fotos_list):
    pdf = InformePDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'CERTIFICADO DE TASACIÓN', 0, 1, 'C')
    pdf.ln(5)
    
    # 1. IDENTIFICACIÓN
    pdf.titulo_seccion("1. IDENTIFICACIÓN")
    pdf.campo_dato("Solicitante:", datos['cliente'])
    pdf.campo_dato("Técnico Tasador:", datos['tasador'])
    pdf.campo_dato("Profesión:", datos['profesion'])
    pdf.campo_dato("Nº Colegiado:", datos['colegiado'])
    pdf.campo_dato("Empresa / Sociedad:", datos['empresa'])
    pdf.ln(2)
    pdf.campo_dato("Ref. Catastral:", datos['ref_catastral'])
    dir_corta = (datos['direccion'][:75] + '..') if len(datos['direccion']) > 75 else datos['direccion']
    pdf.campo_dato("Dirección:", dir_corta)
    pdf.ln(5)

    # 2. DATOS FÍSICOS
    pdf.titulo_seccion("2. DATOS FÍSICOS")
    pdf.set_fill_color(255, 255, 255)
    pdf.cell(60, 7, "Superficie", 1, 0, 'C')
    pdf.cell(60, 7, "Año", 1, 0, 'C')
    pdf.cell(60, 7, "Estado", 1, 1, 'C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 8, f"{datos['superficie']} m2", 1, 0, 'C')
    pdf.cell(60, 8, f"{datos['antiguedad']}", 1, 0, 'C')
    pdf.cell(60, 8, datos['estado'], 1, 1, 'C')
    pdf.ln(5)

    # 3. MERCADO
    pdf.titulo_seccion("3. ANÁLISIS DE MERCADO")
    pdf.set_font('Arial', '', 8)
    pdf.cell(90, 6, "Dirección / Testigo", 1, 0, 'L')
    pdf.cell(30, 6, "Sup (m2)", 1, 0, 'C')
    pdf.cell(30, 6, "Precio", 1, 0, 'C')
    pdf.cell(30, 6, "ValUnit", 1, 1, 'C')
    for t in datos['testigos']:
        pdf.cell(90, 6, t['dir'], 1, 0, 'L')
        pdf.cell(30, 6, str(t['sup']), 1, 0, 'C')
        pdf.cell(30, 6, str(t['precio']), 1, 0, 'C')
        unitario = round(t['precio']/t['sup'], 2) if t['sup'] > 0 else 0
        pdf.cell(30, 6, str(unitario), 1, 1, 'C')
    
    pdf.ln(2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(0, 6, f"Valor Medio Mercado: {datos['precio_m2_zona']} EUR/m2", 0, 1, 'R')
    pdf.ln(5)

    # 4. VALORACIÓN
    pdf.set_draw_color(26, 58, 89)
    pdf.rect(35, pdf.get_y(), 140, 30)
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f"TASACIÓN: {datos['valor_final']} EUR", 0, 1, 'C')
    pdf.set_font('Arial', '', 9)
    pdf.cell(0, 8, f"Fecha: {datetime.date.today().strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(15)
    pdf.cell(0, 10, "Fdo: El Técnico Competente", 0, 1, 'C')

    # 5. FOTOS
    if fotos_list:
        pdf.add_page()
        pdf.titulo_seccion("ANEXO I: FOTOGRAFÍAS")
        y_pos = pdf.get_y() + 10
        for foto in fotos_list:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                    tmp_img.write(foto.getvalue())
                    tmp_path = tmp_img.name
                if y_pos > 220:
                    pdf.add_page()
                    y_pos = 20
                pdf.image(tmp_path, x=30, y=y_pos, w=150)
                y_pos += 110 
            except: pass
    
    return pdf.output(dest='S').encode('latin-1')

# --- APP INTERFAZ PRINCIPAL ---
with st.sidebar:
    st.header("⚙️ Configuración Tasador")
    st.session_state.logo = st.file_uploader("Logotipo Empresa", type=['jpg','png'])
    st.markdown("---")
    tasador = st.text_input("Nombre del Técnico", "Juan Pérez")
    profesion = st.text_input("Profesión", "Arquitecto Técnico")
    colegiado = st.text_input("Nº Colegiado", "A-2938")
    empresa = st.text_input("Empresa / Sociedad", "Tasaciones S.L.")

st.title("🏛️ TasaPro España")
st.markdown("**Herramienta Profesional de Valoración Inmobiliaria ECO/805/2003**")
st.markdown("---")

col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("1. Inmueble")
    rc_input = st.text_input("Ref. Catastral (20 dígitos)", placeholder="9872023VH5797S0001WB")
    if st.button("📡 Buscar Datos Catastro"):
        with st.spinner("Conectando con Sede Electrónica..."):
            datos = consultar_catastro_real(rc_input)
        if "error" in datos:
            st.error(f"❌ {datos['error']}")
        else:
            st.session_state.cat_data = datos
            st.success("✅ Datos oficiales cargados")

if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 0, "ano": 1990, "uso": "Residencial"}

with st.form("main_form"):
    c_dir = st.text_input("Dirección Completa", st.session_state.cat_data["direccion"])
    c1, c2 = st.columns(2)
    sup = c1.number_input("Superficie (m2)", value=int(st.session_state.cat_data["superficie"]))
    ano = c2.number_input("Año Construcción", value=int(st.session_state.cat_data["ano"]))
    estado = st.selectbox("Estado de Conservación", ["Bueno", "Reformado", "A reformar", "Mal estado"])
    cliente = st.text_input("Cliente / Solicitante")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("2. Testigos de Mercado")
    st.info("Introduce 3 inmuebles comparables para el método de comparación.")
    
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        st.markdown("**Testigo 1**")
        t1_eur = st.number_input("Precio T1 (€)", value=180000)
        t1_sup = st.number_input("Sup T1 (m2)", value=90)
    with tc2:
        st.markdown("**Testigo 2**")
        t2_eur = st.number_input("Precio T2 (€)", value=195000)
        t2_sup = st.number_input("Sup T2 (m2)", value=95)
    with tc3:
        st.markdown("**Testigo 3**")
        t3_eur = st.number_input("Precio T3 (€)", value=175000)
        t3_sup = st.number_input("Sup T3 (m2)", value=85)
    
    promedio = ((t1_eur/t1_sup if t1_sup else 0) + (t2_eur/t2_sup if t2_sup else 0) + (t3_eur/t3_sup if t3_sup else 0)) / 3
    st.markdown(f"**Precio Unitario Medio: `{promedio:,.2f} €/m2`**")
    
    st.markdown("---")
    st.subheader("3. Valoración Final")
    
    # MODIFICADO: Campo Coeficiente con Casilla editable y Rango amplio (0.20 - 2.00)
    coef = st.number_input("Coeficiente Homogeneización (0.20 - 2.00)", min_value=0.20, max_value=2.00, value=1.00, step=0.01, format="%.2f", help="Ajuste manual del valor según características específicas.")
    
    valor_final = sup * promedio * coef
    st.metric("VALOR DE TASACIÓN ESTIMADO", f"{valor_final:,.2f} €")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Documentación Adjunta")
    col_doc1, col_doc2 = st.columns(2)
    col_doc1.file_uploader("Adjuntar Nota Simple (PDF)", type="pdf")
    fotos = col_doc2.file_uploader("Adjuntar Fotografías", accept_multiple_files=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.form_submit_button("📄 GENERAR INFORME OFICIAL"):
        if not cliente or sup == 0:
            st.error("⚠️ Por favor, rellena el Cliente y asegúrate de tener Superficie > 0.")
        else:
            datos = {
                "cliente": cliente,
                "tasador": tasador,
                "profesion": profesion,
                "colegiado": colegiado,
                "empresa": empresa,
                "ref_catastral": rc_input,
                "direccion": c_dir, "superficie": sup, "antiguedad": ano, "estado": estado,
                "precio_m2_zona": f"{promedio:,.2f}", "valor_final": f"{valor_final:,.2f}",
                "testigos": [
                    {"dir": "Testigo 1", "sup": t1_sup, "precio": t1_eur},
                    {"dir": "Testigo 2", "sup": t2_sup, "precio": t2_eur},
                    {"dir": "Testigo 3", "sup": t3_sup, "precio": t3_eur}
                ]
            }
            pdf_bytes = generar_pdf_completo(datos, fotos)
            st.success("¡Informe generado correctamente!")
            st.download_button("⬇️ Descargar PDF Firmado", pdf_bytes, "Tasacion_Oficial.pdf", "application/pdf")