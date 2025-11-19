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

# --- FUNCIÓN ROBUSTA CONEXIÓN CATASTRO ---
def get_xml_text(root, paths, default=""):
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        element = root.find(path)
        if element is not None and element.text:
            return element.text
    return default

def consultar_catastro_real(rc_input):
    # --- LIMPIEZA AGRESIVA (La clave para evitar el error) ---
    # 1. Convertir a string por si acaso
    rc = str(rc_input)
    # 2. Quitar espacios en blanco (dentro y fuera)
    rc = rc.replace(" ", "").replace("\t", "").replace("\n", "")
    # 3. Quitar guiones o puntos que a veces la gente pone
    rc = rc.replace("-", "").replace(".", "")
    # 4. Mayúsculas
    rc = rc.upper()
    
    # Verificación longitud antes de llamar
    if len(rc) != 20:
        return {"error": f"Longitud incorrecta: {len(rc)} caracteres. La RC debe tener 20 caracteres exactos (sin espacios)."}

    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            xml_text = response.text
            # Limpiar namespaces molestos
            xml_text = xml_text.replace('xmlns="http://www.catastro.meh.es/"', '')
            xml_text = xml_text.replace('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', '')
            
            root = ET.fromstring(xml_text)
            
            # Verificar errores del servidor
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": f"Catastro rechaza la referencia: {err.text}"}

            # Extracción de datos
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
            except:
                pass 

            return {
                "exito": True,
                "direccion": direccion_completa,
                "superficie": superficie,
                "ano": ano_construccion,
                "uso": get_xml_text(root, [".//bico/bi/de/uso", ".//de/uso"], "Residencial")
            }
        return {"error": "Error de conexión con servidor Catastro (500/404)"}
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
            except:
                pass
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
    pdf.campo_dato("Tasador:", datos['tasador'])
    pdf.campo_dato("Referencia Catastral:", datos['ref_catastral'])
    dir_corta = (datos['direccion'][:75] + '..') if len(datos['direccion']) > 75 else datos['direccion']
    pdf.campo_dato("Dirección:", dir_corta)
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
                if y_pos > 220:
                    pdf.add_page()
                    y_pos = 20
                pdf.image(tmp_path, x=30, y=y_pos, w=150)
                y_pos += 110 
            except: pass
    
    return pdf.output(dest='S').encode('latin-1')

# --- APP ---
with st.sidebar:
    st.header("⚙️ Configuración")
    st.session_state.logo = st.file_uploader("Logo Empresa", type=['jpg','png'])
    tasador = st.text_input("Tasador", "Juan Pérez")

st.title("🏛️ TasaPro Oficial v2.4")

col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("1. Inmueble")
    rc_input = st.text_input("Ref. Catastral (20 dígitos)", placeholder="9872023VH5797S0001WB")
    if st.button("📡 Buscar Datos"):
        with st.spinner("Consultando..."):
            datos = consultar_catastro_real(rc_input)
        if "error" in datos:
            st.error(f"❌ {datos['error']}")
        else:
            st.session_state.cat_data = datos
            st.success("✅ Datos cargados")

if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 0, "ano": 1990, "uso": "Residencial"}

with st.form("main_form"):
    c_dir = st.text_input("Dirección", st.session_state.cat_data["direccion"])
    c1, c2 = st.columns(2)
    sup = c1.number_input("Superficie (m2)", value=int(st.session_state.cat_data["superficie"]))
    ano = c2.number_input("Año", value=int(st.session_state.cat_data["ano"]))
    estado = st.selectbox("Estado", ["Bueno", "Reformado", "A reformar"])
    cliente = st.text_input("Cliente")
    
    st.markdown("---")
    st.subheader("2. Testigos")
    tc1, tc2, tc3 = st.columns(3)
    t1_eur = tc1.number_input("Precio Testigo 1 (€)", value=180000)
    t1_sup = tc1.number_input("Sup T1", value=90)
    t2_eur = tc2.number_input("Precio Testigo 2 (€)", value=195000)
    t2_sup = tc2.number_input("Sup T2", value=95)
    t3_eur = tc3.number_input("Precio Testigo 3 (€)", value=175000)
    t3_sup = tc3.number_input("Sup T3", value=85)
    
    promedio = ((t1_eur/t1_sup) + (t2_eur/t2_sup) + (t3_eur/t3_sup)) / 3
    st.caption(f"Media Mercado: {promedio:,.2f} €/m2")
    
    coef = st.slider("Coeficiente", 0.8, 1.2, 1.0)
    valor_final = sup * promedio * coef
    st.metric("VALOR DE TASACIÓN", f"{valor_final:,.2f} €")
    
    st.file_uploader("Nota Simple", type="pdf")
    fotos = st.file_uploader("Fotos", accept_multiple_files=True)
    
    if st.form_submit_button("📄 GENERAR INFORME"):
        if not cliente or sup == 0:
            st.error("Faltan datos (Cliente o Superficie 0)")
        else:
            datos = {
                "cliente": cliente, "tasador": tasador, "ref_catastral": rc_input,
                "direccion": c_dir, "superficie": sup, "antiguedad": ano, "estado": estado,
                "precio_m2_zona": f"{promedio:,.2f}", "valor_final": f"{valor_final:,.2f}",
                "testigos": [
                    {"dir": "Testigo 1", "sup": t1_sup, "precio": t1_eur},
                    {"dir": "Testigo 2", "sup": t2_sup, "precio": t2_eur},
                    {"dir": "Testigo 3", "sup": t3_sup, "precio": t3_eur}
                ]
            }
            pdf_bytes = generar_pdf_completo(datos, fotos)
            st.download_button("⬇️ Descargar PDF", pdf_bytes, "Tasacion.pdf", "application/pdf")