import streamlit as st
from fpdf import FPDF
import datetime
import requests
import xml.etree.ElementTree as ET
from PIL import Image
import os
import tempfile

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="TasaPro Oficial", page_icon="⚖️", layout="wide")

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

# --- APP ---
with st.sidebar:
    st.header("⚙️ Configuración Tasador")
    st.session_state.logo = st.file_uploader("Logotipo Empresa", type=['jpg','png'])
    st.markdown("---")
    tasador = st.text_input("Nombre del Técnico", "Juan Pérez")
    profesion = st.text_input("Profesión", "Arquitecto Técnico")
    colegiado = st.text_input("Nº Colegiado", "A-2938")
    empresa = st.text_input("Empresa / Sociedad", "Tasaciones S.L.")

st.title("🏛️ TasaPro Oficial v2.5")

col1, col2 = st.columns([1, 2])
with col1: