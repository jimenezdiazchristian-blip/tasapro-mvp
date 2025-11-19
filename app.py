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
    url = f"http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={rc}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            err = root.find(".//lerr/err/des")
            if err is not None:
                return {"error": err.text}

            # Extracción segura de datos (evita el error NoneType)
            calle = get_xml_text(root, ".//domicilio/tv") + " " + get_xml_text(root, ".//domicilio/nv")
            numero = get_xml_text(root, ".//domicilio/pnp")
            municipio = get_xml_text(root, ".//muni/nm")
            provincia = get_xml_text(root, ".//prov/np")
            
            direccion_completa = f"{calle}, {numero}, {municipio} ({provincia})"
            
            superficie = 0
            ano_construccion = 1990 # Valor por defecto seguro
            
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
        return {"error": "Error conexión Catastro"}
    except Exception as e:
        return {"error": f"Excepción: {str(e)}"}

# --- CLASE PDF COMPLETA ---
class InformePDF(FPDF):
    def header(self):
        if 'logo' in st.session_state and st.session_state.logo:
            # Guardar temporalmente logo
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                tmp_logo.write(st.session_state.logo.getvalue())
                tmp_logo_path = tmp_logo.name
            try:
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
    pdf.campo_dato("Dirección:", datos['direccion'][0:60] + "...") # Cortar si es muy larga
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
    pdf.cell(30, 6, "€/m2", 1, 1, 'C')
    
    # Pintar testigos
    for t in datos['testigos']:
        pdf.cell(90, 6, t['dir'], 1, 0, 'L')
        pdf.cell(30, 6, str(t['sup']), 1, 0, 'C')
        pdf.cell(30, 6, str(t['precio']), 1, 0, 'C')
        pdf.cell(30, 6, str(round(t['precio']/t['sup'] if t['sup'] > 0 else 0, 2)), 1, 1, 'C')
    
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
            # Guardar temp
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                tmp_img.write(foto.getvalue())
                tmp_path = tmp_img.name
            
            # Verificar si cabe en la página, si no, nueva página
            if y_pos > 200:
                pdf.add_page()
                y_pos = 20
            
            try:
                pdf.image(tmp_p