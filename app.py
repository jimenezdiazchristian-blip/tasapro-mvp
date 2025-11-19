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
def get_xml_text(root, path, default=""):
    """Ayuda a extraer texto de XML sin que falle si no existe"""
    element = root.find(path)
    if element is not None and element.text:
        return element.text
    return default

def consultar_catastro_real(rc):
    # URL Oficial del servicio de consulta por RC
    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Buscar errores de catastro
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": err.text}

            # Extracción segura de datos
            calle = get_xml_text(root, ".//domicilio/tv") + " " + get_xml_text(root, ".//domicilio/nv")
            numero = get_xml_text(root, ".//domicilio/pnp")
            municipio = get_xml_text(root, ".//muni/nm")
            provincia = get_xml_text(root, ".//prov/np")
            
            direccion_completa = f"{calle}, {numero}, {municipio} ({provincia})"
            
            superficie = 0
            ano_construccion = 1990 # Valor por defecto
            
            try:
                sup_txt = get_xml_text(root, ".//bico/bi/de/supc")
                if sup_txt: superficie = int(sup_txt)
                
                ant_txt = get_xml_text(root, ".//bico/bi/de/ant")
                if ant_txt: ano_construccion = int(ant_txt)
            except:
                pass 

            uso = get_xml_text(root, ".//bico/bi/de/uso", "Residencial")

            return {
                "exito": True,
                "direccion": direccion_completa,
                "superficie": superficie,
                "ano": ano_construccion,
                "uso": uso
            }
        return {"error": "Error conexión Catastro (Red)"}
    except Exception as e:
        return {"error": f"Excepción: {str(e)}"}

# --- CLASE PDF COMPLETA ---
class InformePDF(FPDF):
    def header(self):
        # Intentar poner logo si existe
        if 'logo' in st.session_state and st.session_state.logo:
            try:
                # Guardar temporalmente logo
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                    tmp_logo.write(st.session_state.logo.getvalue())
                    tmp_logo_path = tmp_logo.name
                self.image(tmp_logo_path, 15, 10, 30)
            except:
                pass # Si falla el logo, seguimos sin él
        
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
        self.multi_cell(0, 3, 'DOCUMENTO CONFIDENCIAL. Uso restringido a la finalidad expresada.', 0, 'C')
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
    
    # 1. IDENTIFICACIÓN
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'CERTIFICADO DE TASACIÓN', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.titulo_seccion("1. IDENTIFICACIÓN")
    pdf.campo_dato("Solicitante:", datos['cliente'])
    pdf.campo_dato("Tasador:", datos['tasador'])
    pdf.campo_dato("Referencia Catastral:", datos['ref_catastral'])
    
    # Cortar dirección si es muy larga para que no rompa la tabla
    dir_corta = (datos['direccion'][:75] + '..') if len(datos['direccion']) > 75 else datos['direccion']
    pdf.campo_dato("Dirección:", dir_corta)
    pdf.ln(5)

    # 2. CARACTERÍSTICAS
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

    # 3. TESTIGOS DE MERCADO
    pdf.titulo_seccion("3. ANÁLISIS DE MERCADO (TESTIGOS)")
    pdf.set_font('Arial', '', 8)
    pdf.cell(90, 6, "Dirección / Testigo", 1, 0, 'L')
    pdf.cell(30, 6, "Sup (m2)", 1, 0, 'C')
    pdf.cell(30, 6, "Precio Total", 1, 0, 'C')
    pdf.cell(30, 6, "ValUnit", 1, 1, 'C') # Abreviado
    
    # Pintar testigos
    for t in datos['testigos']:
        pdf.cell(90, 6, t['dir'], 1, 0, 'L')
        pdf.cell(30, 6, str(t['sup']), 1, 0, 'C')
        pdf.cell(30, 6, str(t['precio']), 1, 0, 'C')
        
        unitario = round(t['precio']/t['sup'], 2) if t['sup'] > 0 else 0
        pdf.cell(30, 6, str(unitario), 1, 1, 'C')
    
    pdf.ln(2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(0, 6, f"Valor Medio de Mercado Calculado: {datos['precio_m2_zona']} EUR/m2", 0, 1, 'R')
    pdf.ln(5)

    # 4. VALOR FINAL
    pdf.set_draw_color(26, 58, 89)
    pdf.rect(35, pdf.get_y(), 140, 30)
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f"TASACIÓN: {datos['valor_final']} EUR", 0, 1, 'C')
    pdf.set_font('Arial', '', 9)
    pdf.cell(0, 8, f"Fecha: {datetime.date.today().strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(15)
    
    pdf.cell(0, 10, "Fdo: El Técnico Competente", 0, 1, 'C')

    # 5. ANEXO FOTOGRÁFICO
    if fotos_list:
        pdf.add_page()
        pdf.titulo_seccion("ANEXO I: REPORTAJE FOTOGRÁFICO")
        y_pos = pdf.get_y() + 10
        
        for foto in fotos_list:
            # Guardar temp de manera segura
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                    tmp_img.write(foto.getvalue())
                    tmp_path = tmp_img.name
                
                # Control de salto de página
                if y_pos > 220:
                    pdf.add_page()
                    y_pos = 20
                
                # Aquí estaba el error antes, ahora está protegido:
                pdf.image(tmp_path, x=30, y=y_pos, w=150)
                y_pos += 110 
            except Exception as e:
                # Si una foto falla, la saltamos pero no rompemos la app
                print(f"Error foto: {e}")
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ APP ---
with st.sidebar:
    st.header("⚙️ Configuración")
    st.session_state.logo = st.file_uploader("Logo Empresa", type=['jpg','png'])
    tasador = st.text_input("Tasador", "Juan Pérez")
    
st.title("🏛️ TasaPro Oficial v2.1")

# -- BÚSQUEDA CATASTRO --
col_search, col_res = st.columns([1, 2])
with col_search:
    st.subheader("1. Inmueble")
    rc_input = st.text_input("Ref. Catastral", placeholder="Ej: 9872023VH5797S0001WB")
    if st.button("📡 Buscar Datos Oficiales"):
        if len(rc_input) > 10:
            with st.spinner("Conectando con Sede Electrónica..."):
                datos = consultar_catastro_real(rc_input)
            if "error" in datos:
                st.error(datos["error"])
            else:
                st.session_state.cat_data = datos
                st.success("Datos cargados")
        else:
            st.warning("Referencia corta o inválida")

# Valores por defecto
if 'cat_data' not in st.session_state:
    st.session_state.cat_data = {"direccion": "", "superficie": 100, "ano": 1990, "uso": "Residencial"}

# -- FORMULARIO --
with st.form("main_form"):
    # Datos Inmueble
    c_dir = st.text_input("Dirección", st.session_state.cat_data["direccion"])
    c1, c2, c3 = st.columns(3)
    sup = c1.number_input("Superficie (m2)", value=st.session_state.cat_data["superficie"])
    ano = c2.number_input("Año", value=st.session_state.cat_data["ano"])
    estado = c3.selectbox("Estado", ["Bueno", "Reformado", "A reformar", "Mal estado"])
    cliente = st.text_input("Cliente / Solicitante")
    
    st.markdown("---")
    
    # Testigos
    st.subheader("2. Estudio de Mercado (Testigos)")
    st.info("Introduce 3 inmuebles similares.")
    
    t1_c1, t1_c2, t1_c3 = st.columns([2,1,1])
    t1_dir = t1_c1.text_input("Testigo 1: Dirección", "Calle Ejemplo 1")
    t1_sup = t1_c2.number_input("Sup T1", value=90)
    t1_eur = t1_c3.number_input("Precio T1 (€)", value=180000)
    
    t2_c1, t2_c2, t2_c3 = st.columns([2,1,1])
    t2_dir = t2_c1.text_input("Testigo 2: Dirección", "Calle Ejemplo 2")
    t2_sup = t2_c2.number_input("Sup T2", value=95)
    t2_eur = t2_c3.number_input("Precio T2 (€)", value=195000)
    
    t3_c1, t3_c2, t3_c3 = st.columns([2,1,1])
    t3_dir = t3_c1.text_input("Testigo 3: Dirección", "Calle Ejemplo 3")
    t3_sup = t3_c2.number_input("Sup T3", value=85)
    t3_eur = t3_c3.number_input("Precio T3 (€)", value=175000)
    
    precio_m2_1 = t1_eur / t1_sup if t1_sup else 0
    precio_m2_2 = t2_eur / t2_sup if t2_sup else 0
    precio_m2_3 = t3_eur / t3_sup if t3_sup else 0
    promedio_zona = (precio_m2_1 + precio_m2_2 + precio_m2_3) / 3
    
    st.caption(f"Precio medio: {promedio_zona:,.2f} €/m2")
    
    st.markdown("---")
    st.subheader("3. Valoración Final")
    col_val1, col_val2 = st.columns(2)
    coef = col_val1.slider("Coeficiente Homogeneización", 0.8, 1.2, 1.0, 0.01)
    valor_final = sup * promedio_zona * coef
    
    col_val2.metric("VALOR DE TASACIÓN", f"{valor_final:,.2f} €")
    
    st.markdown("---")
    st.subheader("4. Fotos y Documentación")
    st.file_uploader("Adjuntar Nota Simple (PDF) - (Solo visual en demo)", type="pdf")
    fotos = st.file_uploader("Adjuntar Fotos Inmueble (Se añadirán al PDF)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
    
    submitted = st.form_submit_button("📄 GENERAR INFORME DEFINITIVO")

if submitted:
    if not cliente:
        st.error("Falta el nombre del cliente")
    else:
        datos_informe = {
            "cliente": cliente,
            "tasador": tasador,
            "ref_catastral": rc_input if rc_input else "S/N",
            "direccion": c_dir,
            "superficie": sup,
            "antiguedad": ano,
            "estado": estado,
            "precio_m2_zona": f"{promedio_zona:,.2f}",
            "valor_final": f"{valor_final:,.2f}",
            "testigos": [
                {"dir": t1_dir, "sup": t1_sup, "precio": t1_eur},
                {"dir": t2_dir, "sup": t2_sup, "precio": t2_eur},
                {"dir": t3_dir, "sup": t3_sup, "precio": t3_eur}
            ]
        }
        
        # Generar PDF
        pdf_bytes = generar_pdf_completo(datos_informe, fotos)
        
        st.success("¡Informe generado!")
        st.download_button(
            "⬇️ Descargar PDF Oficial",
            data=pdf_bytes,
            file_name="Tasacion_Oficial.pdf",
            mime="application/pdf"
        )