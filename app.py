import streamlit as st
import anthropic
import fitz
import extract_msg
import json, re, time, base64, os, shutil, zipfile, tempfile, urllib.request, urllib.parse
from pathlib import Path

# ── Configuración de página ───────────────────────────────────
st.set_page_config(
    page_title="DocRename AI",
    page_icon="📄",
    layout="centered"
)

# ── Estilos ───────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    .stApp {
        background-color: #111827;
        color: #e2e8f0;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0d1321 !important;
        border-right: 1px solid #1e2d45;
    }
    .header-block {
        background: linear-gradient(135deg, #1a2540 0%, #111827 100%);
        border: 1px solid #1e2d45;
        border-left: 4px solid #3b82f6;
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }
    .privacy-block {
        background: #0d1321;
        border: 1px solid #1e3a5f;
        border-left: 3px solid #22d3ee;
        border-radius: 8px;
        padding: 1.1rem 1.4rem;
        font-size: 0.88rem;
        color: #94a3b8;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        line-height: 1.75;
    }
    .privacy-block strong { color: #22d3ee; }
    .privacy-block a { color: #22d3ee; text-decoration: none; }
    .stat-box {
        background: #1a2540;
        border: 1px solid #1e2d45;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .stat-num { font-size: 2rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
    .stat-ok   { color: #4ade80; }
    .stat-warn { color: #facc15; }
    .stat-err  { color: #f87171; }
    .stat-label { font-size: 0.72rem; color: #64748b; margin-top: 0.2rem; letter-spacing: 0.05em; text-transform: uppercase; }
    .result-row {
        background: #1a2540;
        border: 1px solid #1e2d45;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.4rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        transition: border-color 0.2s;
    }
    .result-row:hover { border-color: #3b82f6; }
    .badge-ok   { color: #4ade80; }
    .badge-err  { color: #f87171; }
    .limit-note {
        background: #1a2540;
        border: 1px solid #2d3d55;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-size: 0.78rem;
        color: #94a3b8;
        margin-bottom: 1rem;
    }
    .kofi-banner {
        background: #1a2540;
        border: 1px solid #2d3d55;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.78rem;
        color: #94a3b8;
        text-align: center;
        margin-top: 1.5rem;
    }
    .kofi-banner a { color: #fb923c; text-decoration: none; font-weight: 600; }
    .kofi-banner a:hover { text-decoration: underline; }
    .section-divider {
        border: none;
        border-top: 1px solid #1e2d45;
        margin: 1.5rem 0;
    }
    .version-tag {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        color: #3b82f6;
        background: #1a2540;
        border: 1px solid #1e3a5f;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        display: inline-block;
        margin-left: 0.5rem;
        vertical-align: middle;
    }
    /* ── Ocultar texto nativo del file uploader ── */
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span,
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
        display: none !important;
    }
    /* Inyectar texto en español vía pseudo-elementos */
    [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
        content: "Arrastra los archivos aquí";
        display: block;
        font-size: 0.9rem;
        color: #94a3b8;
        font-family: 'IBM Plex Sans', sans-serif;
        margin-bottom: 0.3rem;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div::after {
        content: "Límite 50 MB por archivo · PDF · MSG · ZIP";
        display: block;
        font-size: 0.75rem;
        color: #475569;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    /* Botón "Browse files" → traducir no es posible, pero lo podemos estilizar */
    [data-testid="stFileUploaderDropzone"] button {
        background: #1e3a5f !important;
        color: #93c5fd !important;
        border: 1px solid #2563eb !important;
        border-radius: 6px !important;
        font-size: 0.78rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:

    # Límite
    LIMITE_ARCHIVOS = st.slider(
        "Archivos individuales por sesión (máx. 50)",
        min_value=5, max_value=50, value=30, step=5
    )
    st.markdown("""
    <div style="font-size:0.70rem; color:#475569; margin-top:-0.5rem; line-height:1.5;">
        Aplica a archivos directos.<br>
        ZIPs y MSGs pueden contener hasta <strong style="color:#64748b;">200 PDFs</strong> en total.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Info técnica
    st.markdown("""
    <div style="font-size:0.72rem; color:#475569; line-height:1.7;">
        <p style="margin:0 0 0.3rem 0; color:#64748b; font-weight:600;">Modelo</p>
        <p style="margin:0; font-family:'IBM Plex Mono',monospace;">claude-haiku-4-5</p>
        <p style="margin:0.6rem 0 0.3rem 0; color:#64748b; font-weight:600;">Páginas leídas</p>
        <p style="margin:0;">Solo la primera página de cada PDF</p>
        <p style="margin:0.6rem 0 0.3rem 0; color:#64748b; font-weight:600;">Resolución</p>
        <p style="margin:0;">90 DPI (optimizado para tokens)</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Ko-fi en sidebar
    st.markdown("""
    <div style="background:#1a2540; border:1px solid #fb923c; border-radius:8px; padding:0.9rem 1rem; text-align:center; line-height:1.7;">
        <div style="font-size:0.82rem; color:#94a3b8; margin-bottom:0.4rem;">
            Esta app usa créditos de API con costo real.
        </div>
        <a href="https://ko-fi.com/analyzethis" target="_blank"
           style="color:#fb923c; font-weight:700; text-decoration:none; font-size:1rem;">
            ☕ Invítame un café
        </a>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # GitHub
    st.markdown("""
    <div style="font-size:0.72rem; color:#64748b; text-align:center;">
        <a href="https://github.com/Jon-fen/files_classifier" target="_blank"
           style="color:#64748b; text-decoration:none;">
            🔗 Código abierto en GitHub
        </a>
    </div>
    """, unsafe_allow_html=True)

# ── Header principal ──────────────────────────────────────────
st.markdown("""
<div class="header-block">
    <h1 style="margin:0; font-size:1.35rem; color:#e2e8f0; letter-spacing:0.02em;">
        📄 DocRename AI
        <span class="version-tag">v1.4 beta</span>
    </h1>
    <p style="margin:0.4rem 0 0 0; color:#64748b; font-size:0.82rem;">
        Renombra lotes de PDFs escaneados automáticamente usando visión de IA.<br>
        Extrae tipo de documento, nombre, fecha y genera nombres estandarizados.
    </p>
</div>
""", unsafe_allow_html=True)

# ── API Key solo desde secrets ────────────────────────────────
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
if not api_key:
    st.error("⚠️ API Key no configurada. Si eres administrador, agrégala en Streamlit Secrets.")
    st.stop()

# ── Upload ────────────────────────────────────────────────────
st.markdown(f'<div class="limit-note">📁 Hasta <strong>{LIMITE_ARCHIVOS} archivos individuales</strong> · o ZIPs/MSGs con hasta <strong>200 PDFs</strong> en total · PDF · MSG · ZIP</div>', unsafe_allow_html=True)

archivos = st.file_uploader(
    "Arrastra o selecciona archivos",
    type=["pdf", "msg", "zip"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

# Renombrar botón nativo "Browse files" → "Explorar archivos" vía JS
st.markdown("""
<script>
(function tryRename() {
    const btns = window.parent.document.querySelectorAll(
        '[data-testid="stFileUploaderDropzone"] button'
    );
    if (btns.length > 0) {
        btns.forEach(b => { if (b.innerText.includes('Browse')) b.innerText = 'Seleccionar archivos'; });
    } else {
        setTimeout(tryRename, 300);
    }
})();
</script>
""", unsafe_allow_html=True)

# ── Bloque de privacidad (debajo del uploader) ────────────────
st.markdown("""
<div class="privacy-block">
    🔒 <strong>Privacidad y datos:</strong>
    Esta herramienta usa la <strong>API comercial de Anthropic</strong> (no la versión de consumo).
    Según su política oficial: <em>"By default, we will not use your inputs or outputs from our
    commercial products (e.g. Anthropic API) to train our models."</em>
    — <a href="https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training" target="_blank">
    Anthropic Privacy Center</a><br>
    Los archivos se procesan <strong>solo en memoria</strong> y no se almacenan en ningún servidor propio.
    Solo se lee la <strong>primera página</strong> de cada PDF.
    Aun así, actúa siempre según las políticas de privacidad de tu organización.
</div>
""", unsafe_allow_html=True)

if not archivos:
    st.markdown("""
    <div style="text-align:center; padding: 2rem; color:#334155; font-size:0.85rem;">
        ↑ Sube archivos para comenzar
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.success(f"✅ {len(archivos)} archivo(s) cargados — listos para clasificar")

# ── Prompt genérico ───────────────────────────────────────────
PROMPT = """
Analiza la primera página de este documento escaneado.

IMPORTANTE: El documento es un escáner. Puede tener leve inclinación.
Lee el contenido con máxima precisión ignorando imperfecciones visuales.

Tu tarea: identificar los datos clave para generar un nombre de archivo estandarizado.

Extrae la siguiente información con máxima precisión:

1. TIPO DE DOCUMENTO: Identifica el tipo en 1-3 palabras descriptivas en español.
   Ejemplos: "Permiso", "Certificado Medico", "Resolucion", "Contrato", "Informe",
   "Licencia", "Solicitud", "Oficio", "Memorandum", "Formulario", "Factura", etc.
   Sé específico si puedes (ej: "Licencia Medica" mejor que solo "Licencia").

2. NOMBRE DE PERSONA: El nombre completo del titular o destinatario principal.
   Formato: APELLIDO NOMBRE en mayúsculas. Si no hay persona identificable, usa null.

3. FECHA PRINCIPAL: La fecha más relevante del documento (emisión, vigencia o evento).
   Formato ISO: YYYY-MM-DD. Si hay rango, extrae fecha_desde y fecha_hasta.

4. NÚMERO O CÓDIGO: Si el documento tiene folio, número, código o resolución, extráelo.

5. CONFIANZA: Qué tan legible y claro es el documento (ALTA / MEDIA / BAJA).

Responde ÚNICAMENTE con JSON válido, sin markdown, sin explicaciones:
{
  "tipo"        : "tipo de documento en 1-3 palabras",
  "nombre"      : "APELLIDO NOMBRE o null",
  "fecha_desde" : "YYYY-MM-DD o null",
  "fecha_hasta" : "YYYY-MM-DD o null si no hay rango",
  "numero"      : "folio/número/código o null",
  "confianza"   : "ALTA, MEDIA o BAJA"
}
SOLO el JSON.
"""

# ── Funciones ─────────────────────────────────────────────────

def limpiar_texto(texto, largo=40):
    if not texto: return None
    t = str(texto).strip().title()
    t = re.sub(r'[<>:"/\\|?*]', '', t)
    t = re.sub(r'\s+', '_', t.strip())
    return t[:largo] if t else None

def fmt_fecha(f):
    if not f: return None
    try:
        p = str(f).split('-')
        return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else str(f)
    except: return str(f)

def generar_nombre(d):
    """
    Formato: TIPO_Nombre_Apellido_DD-MM-YYYY[_hasta_DD-MM-YYYY][_NUM].pdf
    """
    partes = []

    # Tipo → prefijo limpio
    tipo = limpiar_texto(d.get('tipo'), largo=30)
    if tipo:
        partes.append(tipo.upper().replace(' ', '_'))
    else:
        partes.append('DOCUMENTO')

    # Nombre persona
    nombre = limpiar_texto(d.get('nombre'), largo=40)
    if nombre:
        partes.append(nombre)

    # Fechas
    f_desde = fmt_fecha(d.get('fecha_desde'))
    f_hasta = fmt_fecha(d.get('fecha_hasta'))
    if f_desde:
        partes.append(f_desde)
    if f_hasta and f_hasta != f_desde:
        partes.append(f"al_{f_hasta}")

    # Número / folio
    numero = d.get('numero')
    if numero:
        num_limpio = re.sub(r'[<>:"/\\|?*\s]', '-', str(numero))[:20]
        partes.append(f"N{num_limpio}")

    nombre_final = '_'.join(filter(None, partes)) + '.pdf'
    # Limitar largo total
    if len(nombre_final) > 200:
        nombre_final = nombre_final[:196] + '.pdf'
    return nombre_final

def pdf_primera_pagina_base64(path):
    """
    Renderiza la primera página a 90 DPI corrigiendo la rotación embebida del PDF.

    Los escáneres y sistemas hospitalarios graban la orientación real en los
    metadatos del PDF (campo /Rotate: 0, 90, 180 o 270). PyMuPDF expone ese
    valor en page.rotation.

    La corrección se aplica mediante una Matrix de contrarotación ANTES de
    escalar, usando fitz.Matrix.prerotate(-rot). Esto produce un pixmap ya
    orientado correctamente sin modificar el archivo original.

    NO se intenta detectar orientación analizando bloques de texto: ese método
    solo funciona con PDFs de texto vectorial, no con PDFs de imagen pura
    (escaneados), que son el caso habitual en contextos hospitalarios.
    """
    doc = fitz.open(path)
    page = doc[0]
    rot = page.rotation  # 0, 90, 180 o 270 — embebido en metadatos del PDF

    # Matriz: contrarotar primero, luego escalar a 90 DPI
    mat = fitz.Matrix(90 / 72, 90 / 72)
    if rot != 0:
        mat = fitz.Matrix(90 / 72, 90 / 72).prerotate(-rot)

    pix = page.get_pixmap(matrix=mat)
    img_b64 = base64.standard_b64encode(pix.tobytes('png')).decode('utf-8')
    doc.close()
    return img_b64, rot

def clasificar(client_ai, img_b64):
    for intento in range(1, 4):
        try:
            r = client_ai.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=300,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': img_b64}},
                        {'type': 'text', 'text': PROMPT}
                    ]
                }]
            )
            texto = r.content[0].text.strip()
            texto = re.sub(r'^```[a-z]*\s*|\s*```$', '', texto, flags=re.MULTILINE).strip()
            datos = json.loads(texto)
            # Guardar uso de tokens
            datos['_tokens'] = r.usage.input_tokens + r.usage.output_tokens
            return datos
        except json.JSONDecodeError:
            if intento < 3: time.sleep(10)
        except Exception as e:
            msg = str(e).lower()
            if 'rate' in msg or '429' in msg:
                time.sleep(60)
            elif intento < 3:
                time.sleep(10)
    return None

# ── Botón de proceso ──────────────────────────────────────────
col_btn, col_info = st.columns([3, 1])
with col_btn:
    iniciar = st.button("🚀 Renombrar documentos", type="primary", use_container_width=True)

# ── Procesamiento: corre UNA VEZ, guarda todo en session_state ───────────────
# En reruns (descarga, estrellas, enviar feedback) Streamlit vuelve a ejecutar
# el script desde el inicio. La clave es NO reprocesar — solo leer session_state.

if iniciar:
    # Limpiar estado anterior si el usuario sube nuevos archivos
    for k in ["fb_zip_bytes","fb_csv_bytes","fb_total","fb_n_ok","fb_n_fallo",
              "fb_log","fb_enviado","fb_estrellas","fb_estrellas_input","fb_comentario"]:
        st.session_state.pop(k, None)

    client_ai = anthropic.Anthropic(api_key=api_key)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_dir = os.path.join(tmpdir, 'pdfs')
        out_dir = os.path.join(tmpdir, 'out')
        os.makedirs(pdf_dir); os.makedirs(out_dir)

        pdfs = []

        def extraer_msg(msg_path, pdf_dir):
            """Extrae todos los PDFs adjuntos de un .msg."""
            encontrados = []
            try:
                msg = extract_msg.Message(msg_path)
                for att in msg.attachments:
                    fname = att.longFilename or att.shortFilename or 'adjunto.pdf'
                    if fname.lower().endswith('.pdf'):
                        fp_pdf = os.path.join(pdf_dir, fname)
                        c = 1
                        while os.path.exists(fp_pdf):
                            base2, ext2 = os.path.splitext(fname)
                            fp_pdf = os.path.join(pdf_dir, f'{base2}_{c}{ext2}')
                            c += 1
                        with open(fp_pdf, 'wb') as fout:
                            fout.write(att.data)
                        encontrados.append(fp_pdf)
            except Exception as e:
                st.warning(f"⚠️ Error leyendo MSG: {e}")
            return encontrados

        for f in archivos:
            ext_f = f.name.lower().rsplit('.', 1)[-1]
            raw_path = os.path.join(tmpdir, f.name)
            with open(raw_path, 'wb') as fp:
                fp.write(f.read())

            if ext_f == 'pdf':
                dest = os.path.join(pdf_dir, f.name)
                shutil.copy2(raw_path, dest)
                pdfs.append(dest)

            elif ext_f == 'msg':
                pdfs.extend(extraer_msg(raw_path, pdf_dir))

            elif ext_f == 'zip':
                try:
                    with zipfile.ZipFile(raw_path, 'r') as zf:
                        for nombre_zip in zf.namelist():
                            base_zip = os.path.basename(nombre_zip)
                            if not base_zip or base_zip.startswith('._') or base_zip.startswith('.') or '__MACOSX' in nombre_zip:
                                continue
                            ext_zip = nombre_zip.lower().rsplit('.', 1)[-1]
                            if ext_zip == 'pdf':
                                datos_zip = zf.read(nombre_zip)
                                base_name = os.path.basename(nombre_zip) or nombre_zip
                                dest = os.path.join(pdf_dir, base_name)
                                c = 1
                                while os.path.exists(dest):
                                    b, e = os.path.splitext(base_name)
                                    dest = os.path.join(pdf_dir, f'{b}_{c}{e}')
                                    c += 1
                                with open(dest, 'wb') as fp:
                                    fp.write(datos_zip)
                                pdfs.append(dest)
                            elif ext_zip == 'msg':
                                datos_zip = zf.read(nombre_zip)
                                base_name = os.path.basename(nombre_zip) or nombre_zip
                                msg_temp = os.path.join(tmpdir, base_name)
                                with open(msg_temp, 'wb') as fp:
                                    fp.write(datos_zip)
                                pdfs.extend(extraer_msg(msg_temp, pdf_dir))
                except Exception as e:
                    st.warning(f"⚠️ Error leyendo ZIP {f.name}: {e}")

        total = len(pdfs)
        if total == 0:
            st.error("No se encontraron PDFs para procesar.")
            st.stop()
        LIMITE_EXTRAIDOS = 200
        if total > LIMITE_EXTRAIDOS:
            st.error(f"❌ Se encontraron {total} PDFs tras descomprimir (límite: {LIMITE_EXTRAIDOS}). Divide el lote en varias sesiones.")
            st.stop()

        st.markdown(f'<div class="limit-note">⏳ Procesando {total} documento(s)…</div>', unsafe_allow_html=True)

        log = []
        progress = st.progress(0)
        status   = st.empty()
        tokens_total = 0

        for i, pdf_path in enumerate(pdfs):
            nombre_orig = os.path.basename(pdf_path)
            status.markdown(f"<span style='color:#64748b; font-size:0.82rem; font-family:monospace;'>⏳ {nombre_orig} ({i+1}/{total})</span>", unsafe_allow_html=True)

            try:
                img_b64, rotacion = pdf_primera_pagina_base64(pdf_path)
                datos = clasificar(client_ai, img_b64)

                if datos is None:
                    nuevo = f'REVISAR_{nombre_orig}'
                    shutil.copy2(pdf_path, os.path.join(out_dir, nuevo))
                    log.append({'original': nombre_orig, 'nuevo': nuevo, 'estado': 'FALLIDO'})
                else:
                    tokens_total += datos.get('_tokens', 0)
                    nuevo_nombre  = generar_nombre(datos)
                    dest = os.path.join(out_dir, nuevo_nombre)
                    c = 1
                    while os.path.exists(dest):
                        base3 = nuevo_nombre.replace('.pdf', '')
                        dest = os.path.join(out_dir, f'{base3}_{c}.pdf')
                        c += 1
                    shutil.copy2(pdf_path, dest)
                    log.append({
                        'original' : nombre_orig,
                        'nuevo'    : os.path.basename(dest),
                        'datos'    : datos,
                        'estado'   : 'OK',
                        'confianza': datos.get('confianza', 'ALTA'),
                        'tipo'     : datos.get('tipo', ''),
                        'rotacion' : rotacion,
                    })

            except Exception as e:
                nuevo = f'REVISAR_{nombre_orig}'
                shutil.copy2(pdf_path, os.path.join(out_dir, nuevo))
                log.append({'original': nombre_orig, 'nuevo': nuevo, 'estado': f'ERROR: {str(e)[:80]}'})

            progress.progress((i + 1) / total)
            time.sleep(0.8)

        status.empty()
        progress.empty()

        n_ok    = sum(1 for r in log if r['estado'] == 'OK')
        n_fallo = sum(1 for r in log if r['estado'] != 'OK')

        # ── Construir ZIP en memoria ──────────────────────────
        zip_buffer = __import__('io').BytesIO()
        csv_lines = ["original,nuevo,tipo,confianza,estado"]
        for r in log:
            tipo_c = r.get('tipo', '').replace(',', ';')
            conf_c = r.get('confianza', '')
            csv_lines.append(f'"{r["original"]}","{r.get("nuevo","")}","{tipo_c}","{conf_c}","{r["estado"]}"')
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for archivo in os.listdir(out_dir):
                zf.write(os.path.join(out_dir, archivo), archivo)
            zf.writestr('_log_renombrado.csv', '\n'.join(csv_lines))

        # ── Guardar TODO en session_state antes de que tmpdir se borre ──
        st.session_state.fb_zip_bytes  = zip_buffer.getvalue()
        st.session_state.fb_csv_bytes  = '\n'.join(csv_lines).encode('utf-8-sig')  # BOM para Excel
        st.session_state.fb_log        = log
        st.session_state.fb_total      = total
        st.session_state.fb_n_ok       = n_ok
        st.session_state.fb_n_fallo    = n_fallo
        st.session_state.fb_tokens     = tokens_total

# ── Mostrar resultados (desde session_state — siempre disponible) ─────────────
if "fb_zip_bytes" in st.session_state:
    log          = st.session_state.fb_log
    n_ok         = st.session_state.fb_n_ok
    n_fallo      = st.session_state.fb_n_fallo
    total        = st.session_state.fb_total
    tokens_total = st.session_state.fb_tokens

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="stat-box"><div class="stat-num stat-ok">{n_ok}</div><div class="stat-label">Renombrados</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-box"><div class="stat-num stat-err">{n_fallo}</div><div class="stat-label">Para revisar</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#38bdf8; font-size:1.4rem;">{tokens_total:,}</div><div class="stat-label">Tokens usados</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### Resultados")
    for r in log:
        if r['estado'] == 'OK':
            badge, cls = '✅', 'badge-ok'
        else:
            badge, cls = '❌', 'badge-err'

        tipo_str  = r.get('tipo', '')
        confianza = r.get('confianza', '')
        rotacion  = r.get('rotacion', 0)
        conf_color = {'ALTA': '#4ade80', 'MEDIA': '#facc15', 'BAJA': '#f87171'}.get(confianza, '#475569')
        conf_html = f'&nbsp;<span style="color:{conf_color}; font-size:0.7rem;">⬤ {confianza}</span>' if confianza else ''
        tipo_html = f'&nbsp;·&nbsp;<span style="color:#94a3b8">{tipo_str}</span>' if tipo_str else ''
        rot_html  = f'&nbsp;·&nbsp;<span style="color:#f59e0b; font-size:0.7rem;" title="Rotación embebida corregida">↻ {rotacion}°</span>' if rotacion else ''

        st.markdown(f"""
        <div class="result-row">
            <span class="{cls}">{badge}</span>{tipo_html}{conf_html}{rot_html}
            <br>
            <span style="color:#334155; font-size:0.72rem;">↳ orig: {r['original']}</span>
            <br>
            <span style="color:#cbd5e1;">↳ nuevo: {r.get('nuevo', r['original'])}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📦 Descargar PDFs renombrados (.zip)",
            data=st.session_state.fb_zip_bytes,
            file_name="documentos_renombrados.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
            key="dl_zip",
        )
    with col_dl2:
        st.download_button(
            label="📋 Descargar log (.csv)",
            data=st.session_state.fb_csv_bytes,
            file_name="log_renombrado.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_csv",
        )



# ── Ko-fi footer ─────────────────────────────────────────────
st.markdown("""
<div class="kofi-banner" style="border-color:#fb923c; padding:1.1rem 1.4rem;">
    <div style="font-size:0.85rem; color:#94a3b8; margin-bottom:0.5rem;">
        Esta app tiene un costo real de API. Si te ahorró tiempo:
    </div>
    <a href="https://ko-fi.com/analyzethis" target="_blank"
       style="color:#fb923c; font-weight:700; font-size:1rem; text-decoration:none;">
        ☕ Invítame un café en Ko-fi
    </a>
    <div style="font-size:0.75rem; color:#475569; margin-top:0.4rem;">Gracias 🙏</div>
</div>
""", unsafe_allow_html=True)

# ── Feedback (fuera del with tmpdir — sobrevive reruns de Streamlit) ──
if "fb_total" in st.session_state:
    SHEETS_WEBHOOK = st.secrets.get("SHEETS_WEBHOOK_URL", None)

    if "fb_enviado" not in st.session_state:
        st.session_state.fb_enviado = False

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    if st.session_state.fb_enviado:
        st.success("¡Gracias por tu feedback! 🙏")
    else:
        st.markdown("""
        <div style="font-size:0.85rem; color:#94a3b8; margin-bottom:0.6rem;">
            ¿Te funcionó? Tu opinión ayuda a mejorar la app.
        </div>
        """, unsafe_allow_html=True)

        nota = st.radio(
            "Calificación",
            options=["⭐ 1 — No funcionó", "⭐⭐ 2 — Mal", "⭐⭐⭐ 3 — Regular",
                     "⭐⭐⭐⭐ 4 — Bien", "⭐⭐⭐⭐⭐ 5 — Excelente"],
            index=4,
            horizontal=True,
            label_visibility="collapsed",
            key="fb_nota",
        )

        st.text_area(
            "Comentario (opcional)",
            placeholder="Ej: los archivos rotados salieron mal / todo perfecto / faltaría que...",
            max_chars=500,
            label_visibility="collapsed",
            key="fb_comentario",
        )

        if st.button("Enviar feedback", use_container_width=False):
            estrellas_val = int(re.search(r"\d", nota).group())
            if not SHEETS_WEBHOOK:
                st.session_state.fb_enviado = True
                st.rerun()
            else:
                try:
                    payload = json.dumps({
                        "timestamp"  : time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                        "estrellas"  : estrellas_val,
                        "comentario" : st.session_state.get("fb_comentario", "").strip() or "—",
                        "archivos"   : st.session_state.fb_total,
                        "ok"         : st.session_state.fb_n_ok,
                        "fallos"     : st.session_state.fb_n_fallo,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        SHEETS_WEBHOOK,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        _ = resp.read()
                    st.session_state.fb_enviado = True
                    st.rerun()
                except Exception as e:
                    st.warning(f"No se pudo enviar el feedback: {e}")

