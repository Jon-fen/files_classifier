import streamlit as st
import anthropic
import fitz
import extract_msg
import holidays
import json, re, time, base64, os, shutil, zipfile, tempfile
from datetime import date, timedelta
from pathlib import Path

# ── Configuración de página ───────────────────────────────────
st.set_page_config(
    page_title="Clasificador de Documentos",
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
        background-color: #0f1117;
        color: #e8e8e8;
    }
    .header-block {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
        border: 1px solid #2a3040;
        border-left: 4px solid #4f9cf9;
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 2rem;
    }
    .stat-box {
        background: #1a1f2e;
        border: 1px solid #2a3040;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
    }
    .stat-num { font-size: 2rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
    .stat-ok   { color: #4ade80; }
    .stat-warn { color: #facc15; }
    .stat-err  { color: #f87171; }
    .stat-label { font-size: 0.75rem; color: #888; margin-top: 0.2rem; }
    .result-row {
        background: #1a1f2e;
        border: 1px solid #2a3040;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
    }
    .badge-ok   { color: #4ade80; }
    .badge-warn { color: #facc15; }
    .badge-err  { color: #f87171; }
    .limit-note {
        background: #1a1f2e;
        border: 1px solid #facc15;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        font-size: 0.8rem;
        color: #facc15;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div class="header-block">
    <h1 style="margin:0; font-size:1.4rem; color:#4f9cf9;">📄 CLASIFICADOR DE DOCUMENTOS</h1>
    <p style="margin:0.3rem 0 0 0; color:#888; font-size:0.85rem;">
        Hospital Dr. Guillermo Grant Benavente · Anthropic Claude Haiku
    </p>
</div>
""", unsafe_allow_html=True)

# ── Límite de archivos ────────────────────────────────────────
LIMITE_ARCHIVOS = 30

# ── API Key desde secrets o input manual ─────────────────────
api_key = None
if "ANTHROPIC_API_KEY" in st.secrets:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
else:
    api_key = st.text_input(
        "🔑 API Key de Anthropic",
        type="password",
        placeholder="sk-ant-...",
        help="Obtén tu key en console.anthropic.com"
    )

if not api_key:
    st.info("Ingresa tu API Key de Anthropic para continuar.")
    st.stop()

# ── Tipo de archivo ───────────────────────────────────────────
tipo_archivo = st.radio(
    "Tipo de archivos a procesar",
    ["📨 Correos .MSG (con PDFs adjuntos)", "📄 PDFs directamente"],
    horizontal=True
)
es_msg = tipo_archivo.startswith("📨")

# ── Upload ────────────────────────────────────────────────────
st.markdown(f'<div class="limit-note">⚠️ Límite: máximo {LIMITE_ARCHIVOS} archivos por sesión</div>', unsafe_allow_html=True)

ext = "msg" if es_msg else "pdf"
archivos = st.file_uploader(
    f"Sube tus archivos .{ext.upper()}",
    type=[ext],
    accept_multiple_files=True
)

if not archivos:
    st.stop()

if len(archivos) > LIMITE_ARCHIVOS:
    st.error(f"❌ Subiste {len(archivos)} archivos. El límite es {LIMITE_ARCHIVOS} por sesión.")
    st.stop()

st.success(f"✅ {len(archivos)} archivo(s) recibidos")

# ── Lógica de procesamiento ───────────────────────────────────

def get_feriados_chile(año):
    return holidays.Chile(years=año)

def contar_dias_habiles(desde_str, hasta_str):
    try:
        desde = date.fromisoformat(desde_str)
        hasta = date.fromisoformat(hasta_str)
        feriados_cl = {}
        for año in set(range(desde.year, hasta.year + 1)):
            feriados_cl.update(get_feriados_chile(año))
        count, d = 0, desde
        while d <= hasta:
            if d.weekday() < 5 and d not in feriados_cl:
                count += 1
            d += timedelta(days=1)
        return count
    except: return None

def contar_dias_corridos(desde_str, hasta_str):
    try:
        return (date.fromisoformat(hasta_str) - date.fromisoformat(desde_str)).days + 1
    except: return None

def validar_dias(datos):
    tipo     = datos.get('tipo', '')
    dias_doc = datos.get('dias')
    f_desde  = datos.get('fecha_desde')
    f_hasta  = datos.get('fecha_hasta')
    if not f_desde or not dias_doc:
        return dias_doc, None, None, 'Sin datos suficientes'
    f_hasta_real = f_hasta or f_desde
    if tipo in ('Feriado Legal', 'Permiso Administrativo'):
        dias_calc = contar_dias_habiles(f_desde, f_hasta_real)
        modo = 'días hábiles'
    elif tipo == 'Permiso Sin Goce':
        dias_calc = contar_dias_corridos(f_desde, f_hasta_real)
        modo = 'días corridos'
    else:
        return dias_doc, None, None, 'No aplica'
    if dias_calc is None:
        return dias_doc, None, None, 'Error al calcular'
    return dias_doc, dias_calc, (int(dias_doc) == dias_calc), f'{modo}: doc={dias_doc}, calc={dias_calc}'

PROMPT = """
Analiza este documento administrativo o médico escaneado en español de un hospital o institución pública chilena.

Clasifica el tipo según estas categorías EXACTAS:
- "No Marcacion"          : justificación de no marcación en reloj biométrico
- "Feriado Legal"         : permiso por feriado legal (días hábiles)
- "Permiso Administrativo": permiso administrativo (días hábiles)
- "Permiso Sin Goce"      : permiso sin goce de sueldo (días corridos)
- "Resolucion"            : resolución oficial numerada
- "Audiometria"           : examen o informe de audiometría
- "Audioimped"            : examen o informe de audioimped (impedanciometría)
- "Otro"                  : cualquier otro tipo no listado

════════════════════════════════════════════════
REGLA CRÍTICA SOBRE FECHAS:
════════════════════════════════════════════════
1. "fecha_solicitud" → Cuando pidió el permiso. ⚠️ NO usar para el nombre.
2. "fecha_desde"     → Primer día EFECTIVO. ✅ Fecha principal.
3. "fecha_hasta"     → Último día EFECTIVO. ✅ Incluir si aparece.

Para No Marcación: fecha efectiva = día en que no marcó.
Para exámenes: fecha efectiva = fecha del examen.
Si solo hay una fecha, asúmela como fecha_desde.
════════════════════════════════════════════════

SOBRE DÍAS: Extrae el valor EXACTO del campo "Cantidad de días".
NO calcules — solo lo que dice el documento. Si no aparece, usa null.

SOBRE SUBTIPO: Si tipo es "Otro", describe el documento en 2-3 palabras
descriptivas en español (ej: Certificado Medico, Licencia Medica, Contrato Honorarios).

Responde ÚNICAMENTE con JSON válido, sin markdown, sin explicaciones.
{
  "tipo"              : "categoría exacta",
  "subtipo"           : "descripción 2-3 palabras si tipo=Otro, si no null",
  "nombre"            : "APELLIDO NOMBRE en mayúsculas tal como aparece",
  "fecha_solicitud"   : "YYYY-MM-DD o null",
  "fecha_desde"       : "YYYY-MM-DD — día efectivo de inicio",
  "fecha_hasta"       : "YYYY-MM-DD — día efectivo de término o null",
  "hora"              : "HH:MM solo para No Marcacion, si no null",
  "entrada_salida"    : "ENTRADA o SALIDA solo para No Marcacion, si no null",
  "dias"              : número entero del documento o null,
  "numero_resolucion" : "número si tipo=Resolucion, si no null",
  "confianza"         : "ALTA, MEDIA o BAJA según qué tan claro es el documento"
}
SOLO el JSON.
"""

def limpiar_nombre_persona(nombre, largo=35):
    if not nombre: return 'Desconocido'
    t = str(nombre).strip().title()
    t = re.sub(r'[<>:"/\\|?*]', '', t)
    t = re.sub(r'\s+', '_', t.strip())
    return t[:largo]

def fmt_fecha(f):
    if not f: return None
    try:
        p = str(f).split('-')
        return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else f
    except: return str(f)

def limpiar_subtipo(texto, largo=20):
    if not texto: return None
    t = str(texto).strip().title()
    t = re.sub(r'[<>:"/\\|?*\s]', '_', t)
    return re.sub(r'_+', '_', t).strip('_')[:largo]

def sufijo_dias(dias, f_desde, f_hasta):
    if dias:
        return f"{dias}dia" if int(dias) == 1 else f"{dias}dias"
    if f_desde and (not f_hasta or f_hasta == f_desde):
        return '1dia'
    return None

def generar_nombre_estandarizado(d):
    tipo    = d.get('tipo', 'Otro')
    nombre  = limpiar_nombre_persona(d.get('nombre'))
    f_desde = fmt_fecha(d.get('fecha_desde'))
    f_hasta = fmt_fecha(d.get('fecha_hasta'))
    dias    = d.get('dias')
    f_hasta_m = f_hasta if f_hasta and f_hasta != f_desde else None
    f_efec    = f_desde or f_hasta
    partes    = []

    if tipo == 'No Marcacion':
        partes += ['NM', nombre]
        if f_efec: partes.append(f_efec)
        es, hora = d.get('entrada_salida'), d.get('hora')
        if es and hora: partes.append(f"{es}-{hora.replace(':', '')}")
        elif es: partes.append(es)
    elif tipo == 'Feriado Legal':
        partes += ['FL', nombre]
        if f_desde: partes.append(f_desde)
        if f_hasta_m: partes.append(f_hasta_m)
        s = sufijo_dias(dias, d.get('fecha_desde'), d.get('fecha_hasta'))
        if s: partes.append(s)
    elif tipo == 'Permiso Administrativo':
        partes += ['PA', nombre]
        if f_desde: partes.append(f_desde)
        if f_hasta_m: partes.append(f_hasta_m)
        s = sufijo_dias(dias, d.get('fecha_desde'), d.get('fecha_hasta'))
        if s: partes.append(s)
    elif tipo == 'Permiso Sin Goce':
        partes += ['PSG', nombre]
        if f_desde: partes.append(f_desde)
        if f_hasta_m: partes.append(f_hasta_m)
        s = sufijo_dias(dias, d.get('fecha_desde'), d.get('fecha_hasta'))
        if s: partes.append(s)
    elif tipo == 'Resolucion':
        partes.append('RESOL')
        if d.get('numero_resolucion'):
            num = str(d['numero_resolucion']).replace('/', '-').replace('\\', '-')
            partes.append(num)
        partes.append(nombre)
        if f_efec: partes.append(f_efec)
    elif tipo == 'Audiometria':
        partes += ['AUDIO', nombre]
        if f_efec: partes.append(f_efec)
    elif tipo == 'Audioimped':
        partes += ['AUDIOIMP', nombre]
        if f_efec: partes.append(f_efec)
    else:
        partes.append('OTRO')
        subtipo = limpiar_subtipo(d.get('subtipo'))
        if subtipo: partes.append(subtipo)
        partes.append(nombre)
        if f_efec: partes.append(f_efec)

    nombre_final = '_'.join(filter(None, partes)) + '.pdf'
    return nombre_final[:196] + '.pdf' if len(nombre_final) > 200 else nombre_final

def pdf_a_imagen_base64(path):
    """Retorna lista de imágenes base64 (máximo 2 páginas)."""
    doc = fitz.open(path)
    imagenes = []
    for n in range(min(2, len(doc))):
        pix = doc[n].get_pixmap(matrix=fitz.Matrix(120/72, 120/72))
        imagenes.append(base64.standard_b64encode(pix.tobytes('png')).decode('utf-8'))
    doc.close()
    return imagenes

def clasificar(client_ai, imagenes):
    """imagenes: lista de strings base64 (1 o 2 páginas)."""
    for intento in range(1, 4):
        try:
            contenido = []
            for img_b64 in imagenes:
                contenido.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': img_b64}})
            contenido.append({'type': 'text', 'text': PROMPT})
            r = client_ai.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=1024,
                messages=[{'role': 'user', 'content': contenido}]
            )
            texto = r.content[0].text.strip()
            texto = re.sub(r'^```[a-z]*\s*|\s*```$', '', texto, flags=re.MULTILINE).strip()
            return json.loads(texto)
        except json.JSONDecodeError:
            if intento < 3: time.sleep(10)
        except Exception as e:
            if 'rate' in str(e).lower() or '429' in str(e):
                time.sleep(60)
            elif intento < 3:
                time.sleep(10)
    return None

# ── Botón de proceso ──────────────────────────────────────────
if st.button("🚀 Clasificar documentos", type="primary", use_container_width=True):

    client_ai = anthropic.Anthropic(api_key=api_key)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_dir  = os.path.join(tmpdir, 'pdfs')
        out_dir  = os.path.join(tmpdir, 'out')
        os.makedirs(pdf_dir); os.makedirs(out_dir)

        # Extraer PDFs
        pdfs = []
        if es_msg:
            for f in archivos:
                msg_path = os.path.join(tmpdir, f.name)
                with open(msg_path, 'wb') as fp: fp.write(f.read())
                try:
                    msg = extract_msg.Message(msg_path)
                    for att in msg.attachments:
                        fname = att.longFilename or att.shortFilename
                        if fname and fname.lower().endswith('.pdf'):
                            fp_pdf = os.path.join(pdf_dir, fname)
                            i = 1
                            while os.path.exists(fp_pdf):
                                base, ext2 = os.path.splitext(fname)
                                fp_pdf = os.path.join(pdf_dir, f'{base}_{i}{ext2}')
                                i += 1
                            with open(fp_pdf, 'wb') as fout: fout.write(att.data)
                            pdfs.append(fp_pdf)
                except Exception as e:
                    st.warning(f"⚠️ Error leyendo {f.name}: {e}")
        else:
            for f in archivos:
                fp = os.path.join(pdf_dir, f.name)
                with open(fp, 'wb') as fp2: fp2.write(f.read())
                pdfs.append(fp)

        total = len(pdfs)
        if total == 0:
            st.error("No se encontraron PDFs para procesar.")
            st.stop()

        st.info(f"📄 {total} PDF(s) a clasificar")

        # Procesar
        log = []
        progress = st.progress(0)
        status   = st.empty()
        log_container = st.container()

        for i, pdf_path in enumerate(pdfs):
            nombre_orig = os.path.basename(pdf_path)
            status.markdown(f"⏳ Procesando `{nombre_orig}` ({i+1}/{total})...")

            try:
                imagenes = pdf_a_imagen_base64(pdf_path)
                datos    = clasificar(client_ai, imagenes)

                if datos is None:
                    nuevo = f'REVISAR_{nombre_orig}'
                    shutil.copy2(pdf_path, os.path.join(out_dir, nuevo))
                    log.append({'original': nombre_orig, 'nuevo': nuevo, 'estado': 'FALLIDO'})
                else:
                    dias_doc, dias_calc, coincide, _ = validar_dias(datos)
                    estado = 'OK_REVISAR_DIAS' if coincide is False else 'OK'
                    nuevo_nombre = generar_nombre_estandarizado(datos)
                    if estado == 'OK_REVISAR_DIAS':
                        nuevo_nombre = nuevo_nombre.replace('.pdf', '_REVISAR_DIAS.pdf')

                    # Evitar duplicados
                    dest = os.path.join(out_dir, nuevo_nombre)
                    c = 1
                    while os.path.exists(dest):
                        base = nuevo_nombre.replace('.pdf', '')
                        dest = os.path.join(out_dir, f'{base}_{c}.pdf')
                        c += 1
                    shutil.copy2(pdf_path, dest)

                    log.append({'original': nombre_orig, 'nuevo': os.path.basename(dest),
                                'datos': datos, 'estado': estado,
                                'dias_doc': dias_doc, 'dias_calc': dias_calc,
                                'confianza': datos.get('confianza', 'ALTA'),
                                'paginas': len(imagenes)})

            except Exception as e:
                nuevo = f'REVISAR_{nombre_orig}'
                shutil.copy2(pdf_path, os.path.join(out_dir, nuevo))
                log.append({'original': nombre_orig, 'nuevo': nuevo,
                            'estado': f'ERROR: {str(e)[:60]}'})

            progress.progress((i + 1) / total)
            time.sleep(1)

        status.markdown("✅ Procesamiento completado")

        # Estadísticas
        n_ok      = len([r for r in log if r['estado'] == 'OK'])
        n_revisar = len([r for r in log if r['estado'] == 'OK_REVISAR_DIAS'])
        n_fallo   = len([r for r in log if r['estado'] not in ('OK', 'OK_REVISAR_DIAS')])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="stat-box"><div class="stat-num stat-ok">{n_ok}</div><div class="stat-label">OK</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="stat-box"><div class="stat-num stat-warn">{n_revisar}</div><div class="stat-label">REVISAR DÍAS</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="stat-box"><div class="stat-num stat-err">{n_fallo}</div><div class="stat-label">FALLIDOS</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Resultados
        st.markdown("### Resultados")
        for r in log:
            if r['estado'] == 'OK':               badge, cls = '✅ OK', 'badge-ok'
            elif r['estado'] == 'OK_REVISAR_DIAS': badge, cls = '🟡 REVISAR DÍAS', 'badge-warn'
            else:                                  badge, cls = '❌ FALLIDO', 'badge-err'
            tipo_str      = r.get('datos', {}).get('tipo', '') if 'datos' in r else ''
            confianza     = r.get('confianza', '')
            paginas       = r.get('paginas', 1)
            conf_color    = {'ALTA': '#4ade80', 'MEDIA': '#facc15', 'BAJA': '#f87171'}.get(confianza, '#888')
            conf_html     = f'&nbsp;·&nbsp;<span style="color:{conf_color};font-size:0.75rem">⬤ {confianza}</span>' if confianza else ''
            pag_html      = f'&nbsp;·&nbsp;<span style="color:#555;font-size:0.75rem">{paginas}p</span>' if paginas > 1 else ''
            st.markdown(f"""
            <div class="result-row">
                <span class="{cls}">{badge}</span>
                {'&nbsp;·&nbsp;<span style="color:#aaa">' + tipo_str + '</span>' if tipo_str else ''}
                {conf_html}{pag_html}
                <br>
                <span style="color:#666">↳</span> {r.get('nuevo', r['original'])}
            </div>
            """, unsafe_allow_html=True)

        # ZIP y descarga
        zip_path = os.path.join(tmpdir, 'pdf_clasificados.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for archivo in os.listdir(out_dir):
                zf.write(os.path.join(out_dir, archivo), archivo)

        with open(zip_path, 'rb') as f:
            st.download_button(
                label="📦 Descargar PDF clasificados (.zip)",
                data=f.read(),
                file_name="pdf_clasificados.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )
