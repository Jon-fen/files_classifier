# Clasificador de Documentos — Hospital Grant Benavente

Aplicación web para clasificar y renombrar PDFs administrativos usando IA (Anthropic Claude Haiku).

## Deploy en Streamlit Cloud (gratis)

### 1. Subir a GitHub
```bash
git init
git add .
git commit -m "clasificador v1"
git remote add origin https://github.com/TU_USUARIO/clasificador-documentos.git
git push -u origin main
```

### 2. Configurar en Streamlit Cloud
1. Ve a [share.streamlit.io](https://share.streamlit.io)
2. Conecta tu cuenta de GitHub
3. New app → elige el repositorio → `app.py`
4. **Settings → Secrets** → agrega:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Con esto la API key queda segura en el servidor, nadie la ve.

### 3. Listo
La app queda en una URL tipo:
`https://TU_USUARIO-clasificador-documentos-app-XXXXX.streamlit.app`

## Límites configurables
En `app.py` línea 47:
```python
LIMITE_ARCHIVOS = 30  # máximo archivos por sesión
```

## Tipos de documento reconocidos
| Prefijo | Tipo |
|---------|------|
| NM | No Marcación |
| FL | Feriado Legal |
| PA | Permiso Administrativo |
| PSG | Permiso Sin Goce |
| RESOL | Resolución |
| AUDIO | Audiometría |
| AUDIOIMP | Audioimped |
| OTRO | Otros (subtipo libre) |
