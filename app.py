import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import os
import tempfile

# --- 1. CONFIGURACIÓN Y ESTÉTICA (DISEÑO DASHBOARD DARK/LIGHT) ---
st.set_page_config(page_title="TasaPro España", page_icon="🏢", layout="wide")

# CSS AVANZADO PARA ESTÉTICA PREMIUM
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

    /* Fuente Global */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1e293b;
    }

    /* --- BARRA LATERAL (SIDEBAR) OSCURA --- */
    section[data-testid="stSidebar"] {
        background-color: #0f172a; /* Azul noche muy oscuro */
    }
    /* Texto en sidebar */
    section[data-testid="stSidebar"] .css-17lntkn, 
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #e2e8f0 !important; /* Blanco sucio para leer bien */
    }
    /* Inputs en sidebar */
    section[data-testid="stSidebar"] .stTextInput > div > div > input {
        background-color: #1e293b;
        color: white;
        border: 1px solid #334155;
    }

    /* --- FONDO PRINCIPAL --- */
    .stApp {
        background-color: #f1f5f9; /* Gris azulado muy suave (Slate 100) */
    }

    /* --- CONTENEDORES Y TARJETAS --- */
    /* Hacemos que el formulario parezca una hoja de papel sobre el escritorio */
    div[data-testid="stForm"] {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #e2e8f0;
    }

    /* Títulos Principales */
    h1 {
        color: #1e3a8a; /* Azul corporativo fuerte */
        font-weight: 800;
    }
    
    /* Subtítulos */
    h3 {
        color: #334155;
        font-weight: 600;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.5rem;
        margin-top: 1rem;
    }

    /* --- INPUTS MODERNOS --- */
    .stTextInput > div > div > input, 
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 0.5rem;
        transition: all 0.3s;
    }
    .stTextInput > div > div > input:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

    /* --- BOTÓN PRINCIPAL (GENERAR) --- */
    .stButton > button {
        background: linear-gradient(to right, #2563eb, #1d4ed8);
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        letter-spacing: 0.05em;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.4);
        transition: transform 0.1s ease-in-out;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.5);
    }

    /* --- TARJETA DE PRECIO FINAL --- */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border-left: 5px solid #2563eb;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    label[data-testid="stMetricLabel"] {
        color: #1e40af !important;
        font-size: 1rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #1e3a8a !important;
        font-size: 2rem !important;
    }

    /* Mensajes de éxito/error más bonitos */
    .stSuccess, .stError, .stWarning {
        border-radius: 8px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)


# --- LÓGICA DE NEGOCIO (MANTENIDA) ---

def get_xml_text(root, paths, default=""):
    if isinstance(paths, str): paths = [paths]
    for path in paths:
        element = root.find(path)
        if element is not None and element.text: return element.text
    return default

def consultar_catastro_real(rc_input):
    rc = str(rc_input).replace(" ", "").replace("\t", "").replace("\n", "").replace("-", "").replace(".", "").upper()
    if len(rc) != 20: return {"error": f"Referencia incorrecta ({len(rc)} caracteres). Deben ser 20."}
    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            xml_text = response.text.replace('xmlns="http://www.catastro.meh.es/"', '').replace('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', '')
            root = ET.fromstring(xml_text)
            err = root.find(".//lerr/err/des")
            if err is not None: return {"error": f"Catastro: {err.text}"}
            
            tv = get_xml_text(root, [".//ldt/dom/tv", ".//domicilio/tv", ".//tv"], "")
            nv = get_xml_text(root, [".//ldt/dom/nv", ".//domicilio/nv", ".//nv"], "")
            calle = f"{tv} {nv}".strip()
            numero = get_xml_text(root, [".//ldt/dom/pnp", ".//domicilio/pnp", ".//pnp"], "")
            municipio = get_xml_text(root, [".//dt/nm", ".//muni/nm", ".//nm"], "")
            provincia = get_xml_text(root, [".//dt/np", ".//prov/np", ".//np"], "")
            
            dir_full = f"{calle}, {numero}, {municipio} ({provincia})" if calle or municipio else "Dirección no disponible"
            
            sup, ano = 0, 1990
            try:
                s = get_xml_text(root, [".//bico/bi/de/supc", ".//de/supc"])
                if s: sup = int(s)
                a = get_xml_text(root, [".//bico/bi/de/ant", ".//de/ant"])
                if a: ano = int(a)
            except: pass
            
            return {"exito": True, "direccion": dir_full, "superficie": sup, "ano": ano}
        return {"error": "Error conexión Catastro"}
    except Exception as e: return {"error": str(e)}

# CLASE PDF
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
    
    pdf.titulo_seccion("1. IDENTIFICACIÓN")
    pdf.campo_dato("Solicitante:", datos['cliente'])
    pdf.campo_dato("Técnico Tasador:", datos['tasador'])
    pdf.campo_dato("Profesión:", datos['profesion'])
    pdf.campo_dato("Nº Colegiado:", datos['colegiado'])
    pdf.campo_dato("Empresa:", datos['empresa'])
    pdf.ln(2)
    pdf.campo_dato("Ref. Catastral:", datos['ref_catastral'])
    pdf.campo_dato("Dirección:", (datos['direccion'][:75] + '..') if len(datos['direccion']) > 75 else datos['direccion'])
    pdf.ln(5)

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

    pdf.titulo_seccion("3. ANÁLISIS DE MERCADO")
    pdf.set_font('Arial', '', 8)
    pdf.cell(90, 6, "Dirección", 1, 0, 'L')
    pdf.cell(30, 6, "Sup", 1, 0, 'C')
    pdf.cell(30, 6, "Precio", 1, 0, 'C')
    pdf.cell(30, 6, "Unitario", 1, 1, 'C')
    for t in datos['testigos']:
        pdf.cell(90, 6, t['dir'], 1, 0, 'L')
        pdf.cell(30, 6, str(t['sup']), 1, 0, 'C')
        pdf.cell(30, 6, str(t['precio']), 1, 0, 'C')
        u = round(t['precio']/t['sup'], 2) if t['sup'] > 0 else 0
        pdf.cell(30, 6, str(u), 1, 1, 'C')
    pdf.ln(2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(0, 6, f"Valor Medio Mercado: {datos['precio_m2_zona']} EUR/m2", 0, 1, 'R')
    pdf.ln(5)

    pdf.set_draw_color(26, 58, 89)
    pdf.rect(35, pdf.get_y(), 140, 30)
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f"TASACIÓN: {datos['valor_final']} EUR", 0, 1, 'C')
    pdf.set_font('Arial', '', 9)
    pdf.cell(0, 8, f"Fecha: {datetime.date.today().strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(15)
    pdf.cell(0, 10, "Fdo: El Técnico Competente", 0, 1, 'C')

    if fotos_list:
        pdf.add_page()
        pdf.titulo_seccion("ANEXO I: FOTOGRAFÍAS")
        y_pos = pdf.get_y() + 10
        for foto in fotos_list:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                    tmp_img.write(foto.getvalue())
                    tmp_path = tmp_img.name
                if y_pos > 220: pdf.add_page(); y_pos = 20
                pdf.image(tmp_path, x=30, y=y_pos, w=150)
                y_pos += 110 
            except: pass
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
with st.sidebar:
    st.markdown("## ⚙️ Panel Técnico")
    st.session_state.logo = st.file_uploader("Logotipo Empresa", type=['jpg','png'])
    st.markdown("---")
    tasador = st.text_input("Nombre del Técnico", "Juan Pérez")
    profesion = st.text_input("Profesión", "Arquitecto Técnico")
    colegiado = st.text_input("Nº Colegiado", "A-2938")
    empresa = st.text_input("Empresa / Sociedad", "Tasaciones S.L.")

st.title("🏛️ TasaPro España")
st.caption("Software Profesional de Valoración Inmobiliaria (ECO/805/2003)")
st.markdown("---")

c1, c2 = st.columns([1, 2])
with c1:
    st.subheader("1. Importación")
    rc_input = st.text_input("Referencia Catastral (20 car.)", placeholder="9872023VH5797S0001WB")
    if st.button("📡 Conectar con Sede Catastro"):
        with st.spinner("Descargando ficha..."):
            d = consultar_catastro_real(rc_input)
        if "error" in d: st.error(d['error'])
        else: st.session_state.cat_data = d; st.success("✅ Datos Oficiales Descargados")

if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 0, "ano": 1990}

with st.form("main_form"):
    st.subheader("2. Datos del Inmueble")
    c_dir = st.text_input("Dirección Completa", st.session_state.cat_data["direccion"])
    cc1, cc2, cc3 = st.columns(3)
    sup = cc1.number_input("Superficie (m2)", value=int(st.session_state.cat_data["superficie"]))
    ano = cc2.number_input("Año Construcción", value=int(st.session_state.cat_data["ano"]))
    estado = cc3.selectbox("Estado Conservación", ["Bueno", "Reformado", "A reformar", "Mal estado"])
    cliente = st.text_input("Cliente / Solicitante")
    
    st.markdown("---")
    st.subheader("3. Testigos de Mercado")
    st.info("Introduce 3 comparables para calcular el valor unitario medio.")
    
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        t1_e = st.number_input("Precio T1 (€)", value=180000)
        t1_s = st.number_input("Sup T1 (m2)", value=90)
    with tc2:
        t2_e = st.number_input("Precio T2 (€)", value=195000)
        t2_s = st.number_input("Sup T2 (m2)", value=95)
    with tc3:
        t3_e = st.number_input("Precio T3 (€)", value=175000)
        t3_s = st.number_input("Sup T3 (m2)", value=85)
    
    prom = ((t1_e/t1_s if t1_s else 0) + (t2_e/t2_s if t2_s else 0) + (t3_e/t3_s if t3_s else 0)) / 3
    st.caption(f"**Valor Unitario Medio Calculado: {prom:,.2f} €/m2**")
    
    st.markdown("---")
    st.subheader("4. Valoración Final")
    
    coef = st.number_input("Coeficiente Homogeneización", 0.20, 2.00, 1.00, 0.01, format="%.2f")
    val_fin = sup * prom * coef
    
    st.metric("VALOR DE TASACIÓN", f"{val_fin:,.2f} €")
    
    st.markdown("#### Documentación")
    col_d1, col_d2 = st.columns(2)
    col_d1.file_uploader("Nota Simple", type="pdf")
    fotos = col_d2.file_uploader("Fotos", accept_multiple_files=True)
    
    if st.form_submit_button("📄 EMITIR INFORME OFICIAL"):
        if not cliente or sup == 0: st.error("Faltan datos obligatorios.")
        else:
            datos = {
                "cliente": cliente, "tasador": tasador, "profesion": profesion, 
                "colegiado": colegiado, "empresa": empresa, "ref_catastral": rc_input,
                "direccion": c_dir, "superficie": sup, "antiguedad": ano, "estado": estado,
                "precio_m2_zona": f"{prom:,.2f}", "valor_final": f"{val_fin:,.2f}",
                "testigos": [{"dir":"T1","sup":t1_s,"precio":t1_e},{"dir":"T2","sup":t2_s,"precio":t2_e},{"dir":"T3","sup":t3_s,"precio":t3_e}]
            }
            pdf = generar_pdf_completo(datos, fotos)
            st.success("¡Informe Generado!")
            st.download_button("⬇️ Descargar PDF", pdf, "Tasacion.pdf", "application/pdf")