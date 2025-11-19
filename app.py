import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import os
import tempfile
import re

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="TasaPro Diagnóstico", page_icon="🛠️", layout="wide")

# ESTILOS (Mantengo tu estética Pro)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1e293b; }
    section[data-testid="stSidebar"] { background-color: #0f172a; }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    .stApp { background-color: #f8fafc; }
    div[data-testid="stForm"] { background-color: #ffffff; padding: 2rem; border-radius: 12px; border: 1px solid #e2e8f0; }
    h1 { color: #1e3a8a; }
    .stButton > button { background: #2563eb; color: white; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE DIAGNÓSTICO ---

def get_xml_text(root, paths, default=""):
    if isinstance(paths, str): paths = [paths]
    for path in paths:
        element = root.find(path)
        if element is not None and element.text: return element.text
    return default

def consultar_catastro_debug(rc_input):
    # 1. LIMPIEZA NUCLEAR
    # Quitamos todo lo que no sea letra o número
    rc = re.sub(r'[^A-Z0-9]', '', str(rc_input).upper())
    
    # 2. CONSTRUCCIÓN DE URL (Oficial del Catastro)
    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    # Devolvemos la URL para que el usuario la vea
    resultado = {
        "url_generada": url,
        "rc_limpia": rc,
        "exito": False,
        "datos": {}
    }

    if len(rc) != 20:
        resultado["error"] = f"Longitud incorrecta ({len(rc)}). Deben ser 20 caracteres."
        return resultado

    try:
        # Hacemos la petición con timeout
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            # Limpiamos namespaces para evitar problemas de lectura
            xml_text = response.text.replace('xmlns="http://www.catastro.meh.es/"', '').replace('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', '')
            root = ET.fromstring(xml_text)
            
            # Buscamos error específico del catastro
            err = root.find(".//lerr/err/des")
            if err is not None:
                resultado["error"] = f"Respuesta del Catastro: {err.text}"
                return resultado

            # Extracción de datos
            tv = get_xml_text(root, [".//ldt/dom/tv", ".//domicilio/tv", ".//tv"], "")
            nv = get_xml_text(root, [".//ldt/dom/nv", ".//domicilio/nv", ".//nv"], "")
            calle = f"{tv} {nv}".strip()
            numero = get_xml_text(root, [".//ldt/dom/pnp", ".//domicilio/pnp", ".//pnp"], "")
            municipio = get_xml_text(root, [".//dt/nm", ".//muni/nm", ".//nm"], "")
            provincia = get_xml_text(root, [".//dt/np", ".//prov/np", ".//np"], "")
            
            direccion_completa = f"{calle}, {numero}, {municipio} ({provincia})"
            if not calle and not municipio: direccion_completa = "Dirección no encontrada en este endpoint"

            # Datos Numéricos
            sup, ano = 0, 1990
            try:
                s = get_xml_text(root, [".//bico/bi/de/supc", ".//de/supc"])
                if s: sup = int(s)
                a = get_xml_text(root, [".//bico/bi/de/ant", ".//de/ant"])
                if a: ano = int(a)
            except: pass

            resultado["exito"] = True
            resultado["datos"] = {
                "direccion": direccion_completa,
                "superficie": sup,
                "ano": ano,
                "uso": get_xml_text(root, [".//bico/bi/de/uso", ".//de/uso"], "Residencial")
            }
            return resultado
            
        else:
            resultado["error"] = f"Error Servidor HTTP: {response.status_code}"
            return resultado

    except Exception as e:
        resultado["error"] = f"Error Técnico: {str(e)}"
        return resultado

# --- CLASE PDF (VERSION OFICIAL) ---
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
        self.set_y(-20); self.set_font('Arial', '', 7); self.multi_cell(0,3,'Documento Confidencial',0,'C'); self.set_y(-10); self.cell(0,10,f'Página {self.page_no()}',0,0,'R')
    def titulo_seccion(self, titulo):
        self.set_font('Arial', 'B', 11); self.set_fill_color(240, 240, 245); self.cell(0, 8, f"  {titulo.upper()}", 0, 1, 'L', 1); self.ln(4)
    def campo_dato(self, etiqueta, valor):
        self.set_font('Arial', 'B', 9); self.cell(50, 6, etiqueta, 0, 0); self.set_font('Arial', '', 9); self.cell(0, 6, str(valor), 0, 1)

def generar_pdf_completo(datos, fotos_list):
    pdf = InformePDF(); pdf.add_page(); pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, f'CERTIFICADO DE TASACIÓN', 0, 1, 'C'); pdf.ln(5)
    pdf.titulo_seccion("1. IDENTIFICACIÓN"); pdf.campo_dato("Solicitante:", datos['cliente']); pdf.campo_dato("Tasador:", datos['tasador']); pdf.campo_dato("Ref. Catastral:", datos['ref_catastral']); pdf.campo_dato("Dirección:", datos['direccion'][:75]); pdf.ln(5)
    pdf.titulo_seccion("2. DATOS FÍSICOS"); pdf.cell(60, 7, "Superficie", 1, 0, 'C'); pdf.cell(60, 7, "Año", 1, 0, 'C'); pdf.cell(60, 7, "Estado", 1, 1, 'C'); pdf.set_font('Arial', '', 10); pdf.cell(60, 8, f"{datos['superficie']} m2", 1, 0, 'C'); pdf.cell(60, 8, f"{datos['antiguedad']}", 1, 0, 'C'); pdf.cell(60, 8, datos['estado'], 1, 1, 'C'); pdf.ln(5)
    pdf.titulo_seccion("3. VALORACIÓN"); pdf.set_font('Arial', 'B', 18); pdf.cell(0, 10, f"TASACIÓN: {datos['valor_final']} EUR", 0, 1, 'C'); pdf.ln(15); pdf.set_font('Arial', '', 9); pdf.cell(0, 10, "Fdo: El Técnico Competente", 0, 1, 'C')
    if fotos_list:
        pdf.add_page(); pdf.titulo_seccion("ANEXO I: FOTOGRAFÍAS"); y=40
        for f in fotos_list:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t: t.write(f.getvalue()); n=t.name
                if y>220: pdf.add_page(); y=20
                pdf.image(n, x=30, y=y, w=150); y+=110
            except: pass
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
with st.sidebar:
    st.header("⚙️ Panel Técnico")
    st.session_state.logo = st.file_uploader("Logo Empresa", type=['jpg','png'])
    st.markdown("---")
    tasador = st.text_input("Tasador", "Juan Pérez")
    profesion = st.text_input("Profesión", "Arquitecto Técnico")
    colegiado = st.text_input("Nº Colegiado", "A-001")
    empresa = st.text_input("Empresa", "Tasaciones S.L.")

st.title("🏛️ TasaPro - Modo Diagnóstico")
st.info("Si el Catastro falla, usaremos este panel para verificar la conexión.")

c1, c2 = st.columns([1, 2])
with c1:
    st.subheader("1. Conexión Catastro")
    rc_input = st.text_input("Referencia Catastral", placeholder="Ej: 9872023VH5797S0001WB")
    
    if st.button("📡 PROBAR CONEXIÓN"):
        with st.spinner("Conectando..."):
            res = consultar_catastro_debug(rc_input)
            
            st.markdown("---")
            st.write("**Diagnóstico:**")
            
            # MOSTRAMOS EL ENLACE PARA QUE EL USUARIO COMPRUEBE
            st.markdown(f"🔗 **[Haz clic aquí para ver lo que devuelve el Catastro]({res['url_generada']})**")
            st.caption("☝️ Si haces clic y ves un mensaje de error en rojo (XML), es que la referencia no es válida para la Sede Electrónica.")
            
            if res["exito"]:
                st.success("✅ ¡CONEXIÓN EXITOSA!")
                st.session_state.cat_data = res["datos"]
            else:
                st.error(f"❌ Error detectado: {res.get('error')}")
                st.write(f"Referencia enviada (limpia): `{res['rc_limpia']}`")

if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 0, "ano": 1990}

with st.form("main_form"):
    st.write("---")
    st.subheader("Datos del Informe")
    c_dir = st.text_input("Dirección", st.session_state.cat_data["direccion"])
    cc1, cc2 = st.columns(2)
    sup = cc1.number_input("Superficie (m2)", value=int(st.session_state.cat_data["superficie"]))
    ano = cc2.number_input("Año", value=int(st.session_state.cat_data["ano"]))
    cliente = st.text_input("Cliente")
    
    st.subheader("Valoración")
    col_val1, col_val2 = st.columns(2)
    m2_val = col_val1.number_input("Valor Mercado (€/m2)", value=2000.0)
    coef = col_val2.number_input("Coeficiente (0.20-2.00)", 0.20, 2.00, 1.00, 0.01)
    
    val_fin = sup * m2_val * coef
    st.metric("Valor Final", f"{val_fin:,.2f} €")
    
    fotos = st.file_uploader("Fotos", accept_multiple_files=True)
    
    if st.form_submit_button("📄 GENERAR PDF"):
        datos = {
            "cliente": cliente, "tasador": tasador, "profesion": profesion, 
            "colegiado": colegiado, "empresa": empresa, "ref_catastral": rc_input,
            "direccion": c_dir, "superficie": sup, "antiguedad": ano, "estado": "Bueno",
            "valor_final": f"{val_fin:,.2f}"
        }
        pdf = generar_pdf_completo(datos, fotos)
        st.download_button("⬇️ Descargar PDF", pdf, "Tasacion.pdf", "application/pdf")