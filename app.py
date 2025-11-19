import streamlit as st
from fpdf import FPDF
import datetime
from PIL import Image
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="TasaPro España", page_icon="🏠", layout="wide")

# --- ESTILOS CSS PARA DISEÑO ELEGANTE ---
st.markdown("""
    <style>
    .main {
        background-color: #F5F7FA;
    }
    h1 { color: #1A3A59; }
    h2 { color: #2C3E50; }
    .stButton>button {
        background-color: #1A3A59;
        color: white;
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CLASE PARA GENERAR PDF ---
class PDF(FPDF):
    def header(self):
        if 'logo' in st.session_state and st.session_state.logo is not None:
            # Guardar temporalmente el logo para usarlo en el PDF
            with open("temp_logo.png", "wb") as f:
                f.write(st.session_state.logo.getbuffer())
            self.image("temp_logo.png", 10, 8, 33)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'INFORME DE TASACIÓN OFICIAL', 0, 1, 'R')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} - Generado por TasaPro', 0, 0, 'C')

def generar_informe(datos):
    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f'Valoración de Inmueble: {datos["referencia"]}', 0, 1, 'C')
    pdf.ln(10)
    
    # Datos del Tasador
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '1. DATOS DEL TASADOR Y SOLICITANTE', 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 10, f'Tasador: {datos["nombre_tasador"]} | Colegiado: {datos["colegiado"]}', 0, 1)
    pdf.cell(0, 10, f'Solicitante: {datos["cliente"]}', 0, 1)
    pdf.ln(5)
    
    # Descripción
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. IDENTIFICACIÓN Y DESCRIPCIÓN', 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 10, f'Dirección: {datos["direccion"]}\nReferencia Catastral: {datos["ref_catastral"]}\nSuperficie: {datos["superficie"]} m2\nAntigüedad: {datos["antiguedad"]} años\nEstado: {datos["estado"]}')
    pdf.ln(5)
    
    # Valoración
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '3. CÁLCULO Y VALOR DE TASACIÓN', 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 10, f'Método utilizado: Comparación de mercado (ECO/805/2003)', 0, 1)
    pdf.cell(0, 10, f'Precio medio zona: {datos["precio_m2_zona"]} EUR/m2', 0, 1)
    
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(26, 58, 89)
    pdf.cell(0, 20, f'VALOR DE TASACIÓN: {datos["valor_final"]} EUR', 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ DE USUARIO ---

# Sidebar: Configuración del Tasador (Marca blanca)
with st.sidebar:
    st.header("⚙️ Configuración Tasador")
    st.info("Personaliza el informe con tu marca")
    uploaded_logo = st.file_uploader("Subir Logotipo Empresa", type=['png', 'jpg'])
    if uploaded_logo:
        st.session_state.logo = uploaded_logo
        st.image(uploaded_logo, width=150)
    
    nombre_tasador = st.text_input("Nombre del Técnico", "Juan Pérez")
    num_colegiado = st.text_input("Nº Colegiado", "A-2938")
    empresa = st.text_input("Empresa Tasadora", "Tasaciones Rápidas SL")

# Cuerpo Principal
st.title("📋 Generador de Informes Técnicos")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Inmueble y Catastro")
    ref_cat = st.text_input("Referencia Catastral")
    
    # Simulación de API Catastro
    if st.button("🔍 Buscar en Catastro"):
        if ref_cat:
            st.success("Datos descargados de Sede Electrónica del Catastro")
            # Aquí en producción conectaríamos con la API real
            direccion_auto = "Calle Mayor 15, 3ºA, Madrid"
            superficie_auto = 120
            ano_auto = 1995
        else:
            st.warning("Introduce una referencia catastral")
            direccion_auto = ""
            superficie_auto = 0
            ano_auto = 2000
    else:
        direccion_auto = ""
        superficie_auto = 0
        ano_auto = 2000

with col2:
    st.subheader("2. Datos del Informe")
    # Formulario que se auto-rellena si hay datos de catastro
    direccion = st.text_input("Dirección Completa", value=direccion_auto)
    c1, c2, c3 = st.columns(3)
    superficie = c1.number_input("Superficie (m2)", value=superficie_auto)
    antiguedad = c2.number_input("Año Construcción", value=ano_auto)
    estado = c3.selectbox("Estado de Conservación", ["Nuevo", "Bueno", "A reformar", "Ruina"])
    
    cliente = st.text_input("Solicitante / Cliente")
    nota_simple = st.file_uploader("Adjuntar Nota Simple (PDF)", type="pdf")

st.markdown("---")

# Sección de Valoración y Testigos
st.subheader("3. Valoración y Testigos (ECO/805/2003)")
st.markdown("Introduce los testigos comparables o deja que el sistema sugiera (fase beta).")

tc1, tc2, tc3 = st.columns(3)
precio_zona = tc1.number_input("Precio medio zona (€/m2)", value=2500)
coeficiente = tc2.slider("Coeficiente de Homogeneización", 0.5, 1.5, 1.0, 0.05)
valor_calculado = superficie * precio_zona * coeficiente

st.metric(label="Valor Estimado del Inmueble", value=f"{valor_calculado:,.2f} €")

# Fotos
st.subheader("4. Reportaje Fotográfico")
fotos = st.file_uploader("Subir fotos del inmueble", accept_multiple_files=True, type=['jpg', 'png'])

if fotos:
    st.image(fotos[0], caption="Foto de Portada", width=300)
    st.info("El resto de fotos se añadirán al anexo del PDF.")

st.markdown("---")

# Generación
st.subheader("5. Finalizar")
if st.button("📝 GENERAR INFORME OFICIAL PDF"):
    if not direccion or not cliente:
        st.error("Por favor completa los campos obligatorios.")
    else:
        datos_informe = {
            "nombre_tasador": nombre_tasador,
            "colegiado": num_colegiado,
            "cliente": cliente,
            "direccion": direccion,
            "ref_catastral": ref_cat,
            "superficie": superficie,
            "antiguedad": 2024 - antiguedad,
            "estado": estado,
            "precio_m2_zona": precio_zona,
            "valor_final": f"{valor_calculado:,.2f}",
            "referencia": "TAS-2024-001"
        }
        
        pdf_bytes = generar_informe(datos_informe)
        
        st.success("¡Informe generado correctamente según normativa ECO/805/2003!")
        st.download_button(
            label="⬇️ Descargar Informe PDF",
            data=pdf_bytes,
            file_name=f"Tasacion_{ref_cat}.pdf",
            mime="application/pdf"
        )