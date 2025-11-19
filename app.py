import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import os
import tempfile
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TasaPro España", page_icon="🏢", layout="wide")

# ESTILOS PRO (Mantenemos tu diseño)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1e293b; }
    section[data-testid="stSidebar"] { background-color: #0f172a; }
    section[data-testid="stSidebar"] * { color: #f1f5f9 !important; }
    section[data-testid="stSidebar"] input { background-color: #1e293b !important; color: white !important; }
    .stApp { background-color: #f8fafc; }
    div[data-testid="stForm"] { background-color: white; padding: 2rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    h1 { color: #1e3a8a; font-weight: 800; }
    .stButton > button { background: linear-gradient(to right, #2563eb, #1d4ed8); color: white; font-weight: bold; border: none; border-radius: 8px; height: 3rem; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE CONEXIÓN (ACTUALIZADA A HTTPS) ---

def get_xml_text(root, paths, default=""):
    if isinstance(paths, str): paths = [paths]
    for path in paths:
        element = root.find(path)
        if element is not None and element.text: return element.text
    return default

def consultar_catastro_final(rc_input):
    # 1. LIMPIEZA
    rc = re.sub(r'[^A-Z0-9]', '', str(rc_input).upper())
    
    # 2. DETECTOR DE ERRORES COMUNES
    if len(rc) == 14:
        return {"error": "⚠️ ¡CUIDADO! Has introducido 14 caracteres. Esa es la referencia de la PARCELA. Necesitas la del INMUEBLE (20 caracteres). Mira en el recibo del IBI o pulsa 'Cargar Ejemplo'."}
    
    if len(rc) != 20:
        return {"error": f"Longitud incorrecta ({len(rc)}). La referencia debe tener 20 caracteres exactos."}

    # 3. URL OFICIAL (Actualizada a HTTPS para mayor seguridad)
    url = f"https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    try:
        # Usamos verify=False temporalmente porque el certificado del gobierno a veces da problemas en Python directo
        response = requests.get(url, timeout=15, verify=False) 
        
        if response.status_code == 200:
            xml_text = response.text.replace('xmlns="http://www.catastro.meh.es/"', '').replace('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', '')
            root = ET.fromstring(xml_text)
            
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": f"Catastro dice: {err.text}"}

            # Datos
            tv = get_xml_text(root, [".//ldt/dom/tv", ".//domicilio/tv", ".//tv"], "")
            nv = get_xml_text(root, [".//ldt/dom/nv", ".//domicilio/nv", ".//nv"], "")
            calle = f"{tv} {nv}".strip()
            numero = get_xml_text(root, [".//ldt/dom/pnp", ".//domicilio/pnp", ".//pnp"], "")
            municipio = get_xml_text(root, [".//dt/nm", ".//muni/nm", ".//nm"], "")
            provincia = get_xml_text(root, [".//dt/np", ".//prov/np", ".//np"], "")
            
            dir_full = f"{calle}, {numero}, {municipio} ({provincia})"
            if not calle and not municipio: dir_full = "Dirección no detallada en este servicio"
            
            sup, ano = 0, 1990
            try:
                s = get_xml_text(root, [".//bico/bi/de/supc", ".//de/supc"])
                if s: sup = int(s)
                a = get_xml_text(root, [".//bico/bi/de/ant", ".//de/ant"])
                if a: ano = int(a)
            except: pass
            
            return {"exito": True, "direccion": dir_full, "superficie": sup, "ano": ano}
        return {"error": f"Error HTTP {response.status_code}"}
    except Exception as e: return {"error": f"Error conexión: {str(e)}"}

# --- CLASE PDF ---
class InformePDF(FPDF):
    def header(self):
        if 'logo' in st.session_state and st.session_state.logo:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t:
                    t.write(st.session_state.logo.getvalue()); n=t.name
                self.image(n, 15, 10, 30)
            except: pass
        self.set_font('Times', 'B', 10); self.set_text_color(100); self.cell(0,5,'INFORME TÉCNICO VALORACIÓN',0,1,'R')
        self.set_font('Times', '', 8); self.cell(0,5,'Orden ECO/805/2003',0,1,'R'); self.set_draw_color(26,58,89); self.line(15,30,195,30); self.ln(25)
    def footer(self):
        self.set_y(-20); self.set_draw_color(200); self.line(15,275,195,275); self.set_font('Arial','',7); self.multi_cell(0,3,'Documento Confidencial',0,'C'); self.set_y(-10); self.cell(0,10,f'Página {self.page_no()}',0,0,'R')
    def titulo(self, t): self.set_font('Arial','B',11); self.set_fill_color(240,240,245); self.set_text_color(26,58,89); self.cell(0,8,f"  {t}",0,1,'L',1); self.ln(4)
    def dato(self, e, v): self.set_font('Arial','B',9); self.set_text_color(50); self.cell(50,6,e,0,0); self.set_font('Arial','',9); self.set_text_color(0); self.cell(0,6,str(v),0,1)

def generar_pdf(d, fotos):
    pdf = InformePDF(); pdf.add_page()
    pdf.set_font('Arial','B',14); pdf.cell(0,10,'CERTIFICADO DE TASACIÓN',0,1,'C'); pdf.ln(5)
    pdf.titulo("1. IDENTIFICACIÓN"); pdf.dato("Solicitante:", d['cliente']); pdf.dato("Tasador:", d['tasador']); pdf.dato("Colegiado:", d['colegiado']); pdf.dato("RC:", d['ref_catastral']); pdf.dato("Dirección:", d['direccion'][:70]); pdf.ln(5)
    pdf.titulo("2. DATOS FÍSICOS"); pdf.cell(60,7,"Superficie",1,0,'C'); pdf.cell(60,7,"Año",1,0,'C'); pdf.cell(60,7,"Estado",1,1,'C'); pdf.set_font('Arial','',10); pdf.cell(60,8,f"{d['superficie']} m2",1,0,'C'); pdf.cell(60,8,f"{d['antiguedad']}",1,0,'C'); pdf.cell(60,8,d['estado'],1,1,'C'); pdf.ln(5)
    pdf.titulo("3. VALORACIÓN"); pdf.set_font('Arial','B',18); pdf.set_text_color(26,58,89); pdf.cell(0,10,f"{d['valor_final']} EUR",0,1,'C'); pdf.ln(10); pdf.set_font('Arial','',9); pdf.set_text_color(0); pdf.cell(0,10,"Fdo: El Técnico Competente",0,1,'C')
    if fotos:
        pdf.add_page(); pdf.titulo("ANEXO I: FOTOS"); y=40
        for f in fotos:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t: t.write(f.getvalue()); n=t.name
                if y>220: pdf.add_page(); y=20
                pdf.image(n,x=30,y=y,w=150); y+=110
            except: pass
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 0, "ano": 1990}

# Callback Botón
def cargar_demo():
    st.session_state.rc_temp = "9872023VH5797S0001WB"

with st.sidebar:
    st.markdown("## ⚙️ Panel Técnico")
    st.session_state.logo = st.file_uploader("Logotipo", type=['jpg','png'])
    st.markdown("---")
    tasador = st.text_input("Tasador", "Juan Pérez")
    profesion = st.text_input("Profesión", "Arquitecto Técnico")
    colegiado = st.text_input("Nº Colegiado", "A-2938")
    empresa = st.text_input("Empresa", "Tasaciones S.L.")

st.title("🏛️ TasaPro España v3.2")
st.markdown("### Conexión Sede Electrónica")

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    st.write("")
    st.write("")
    st.button("📝 Cargar Ejemplo", on_click=cargar_demo)

with c2:
    # Input controlado
    val_inicial = st.session_state.get("rc_temp", "")
    rc_input = st.text_input("Referencia Catastral (20 dígitos)", value=val_inicial)

with c3:
    st.write("")
    st.write("")
    buscar = st.button("📡 BUSCAR DATOS")

if buscar:
    with st.spinner("Conectando con Servidor OVC (HTTPS)..."):
        res = consultar_catastro_final(rc_input)
    if "error" in res:
        st.error(res['error'])
    else:
        st.session_state.cat_data = res
        st.success(f"✅ Datos recuperados: {res['direccion']}")

# FORMULARIO
with st.form("main_form"):
    st.subheader("Datos del Inmueble")
    c_dir = st.text_input("Dirección", st.session_state.cat_data["direccion"])
    
    k1, k2, k3 = st.columns(3)
    sup = k1.number_input("Superficie (m2)", value=int(st.session_state.cat_data["superficie"]))
    ano = k2.number_input("Año", value=int(st.session_state.cat_data["ano"]))
    estado = k3.selectbox("Estado", ["Bueno", "Reformado", "A reformar"])
    cliente = st.text_input("Cliente")
    
    st.subheader("Valoración")
    col_v1, col_v2 = st.columns(2)
    m2 = col_v1.number_input("Valor Mercado (€/m2)", value=2000.0)
    coef = col_v2.number_input("Coeficiente (0.20-2.00)", 0.20, 2.00, 1.00, 0.01)
    
    val = sup * m2 * coef
    st.metric("VALOR DE TASACIÓN", f"{val:,.2f} €")
    
    st.markdown("---")
    f1, f2 = st.columns(2)
    f1.file_uploader("Nota Simple", type="pdf")
    fotos = f2.file_uploader("Fotos", accept_multiple_files=True)
    
    if st.form_submit_button("📄 GENERAR INFORME"):
        if not cliente or sup == 0:
            st.error("Faltan datos obligatorios")
        else:
            d = {
                "cliente": cliente, "tasador": tasador, "profesion": profesion,
                "colegiado": colegiado, "empresa": empresa, "ref_catastral": rc_input,
                "direccion": c_dir, "superficie": sup, "antiguedad": ano, "estado": estado,
                "valor_final": f"{val:,.2f}"
            }
            pdf = generar_pdf(d, fotos)
            st.download_button("⬇️ Descargar PDF", pdf, "Tasacion.pdf", "application/pdf")