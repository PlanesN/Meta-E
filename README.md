# Metadata Extractor (Flask + ExifTool)

Aplicación web para subir archivos y extraer metadata con `exiftool`.

## Seguridad y producción

Este proyecto ya está preparado para producción con:

- `debug=False`
- timeout de ejecución de ExifTool (`EXIFTOOL_TIMEOUT_SECONDS`)
- subida de archivos sin límite de tamaño en app y Nginx
- headers básicos de seguridad HTTP
- despliegue recomendado con Gunicorn + systemd + Nginx

## Requisitos

- Python 3.9+
- ExifTool instalado en el sistema

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libimage-exiftool-perl nginx certbot python3-certbot-nginx
```

### macOS (desarrollo local)

```bash
brew install exiftool
```

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Abrir en navegador: `http://127.0.0.1:5050`

## Despliegue en Ubuntu Server (con Docker, Traefik y Matrix existentes)

Dado que en tu servidor ya cuentas con Traefik, Matrix y Docker, el proceso es mucho más ágil. Usaremos `/opt` para la instalación, que es el estándar para servicios en producción.

### 1) Preparar y subir el proyecto al servidor

Tienes dos opciones dependiendo de si tu servidor tiene acceso a Git o si prefieres subirlo manualmente:

#### Opción A: Clonar con Git (Recomendado si hay acceso)
Si tu servidor tiene acceso al repositorio:
```bash
# Conéctate por SSH
ssh usuario@IP_DEL_SERVIDOR

# Clonar directamente en /opt (necesitarás sudo para la carpeta)
sudo mkdir -p /opt/meta-e
sudo chown $USER:$USER /opt/meta-e
git clone URL_DEL_REPOSITORIO /opt/meta-e
cd /opt/meta-e
```

#### Opción B: Subir archivo comprimido (Si no hay acceso a Git)
Desde tu terminal local:
```bash
zip -r meta-e.zip . -x ".git/*" ".DS_Store" "__pycache__/*"
scp meta-e.zip usuario@IP_DEL_SERVIDOR:/tmp/
```
Luego en el servidor:
```bash
sudo mkdir -p /opt/meta-e
sudo chown $USER:$USER /opt/meta-e
unzip /tmp/meta-e.zip -d /opt/meta-e
cd /opt/meta-e
```

### 2) Ajustar `docker-compose.yml`

Abre el archivo para asegurar la integración con tu red de Traefik:

```bash
nano docker-compose.yml
```

**Puntos clave a revisar:**
1. **Red externa:** Al final del archivo, en `networks.traefik-net.external`, asegúrate de que el nombre sea el que usa tu Traefik (ej. `proxy` o `web`).
2. **Dominio:** Cambia `Host(`meta.mexicosadecv.com.mx`)` por el tuyo.
3. **SSL Resolver:** Cambia `certresolver=myresolver` por el tuyo (ej. `letsencrypt`).

### 4) Levantar el servicio

Crea el archivo de entorno y lanza el contenedor:

```bash
cp .env.example .env
docker compose up -d --build
```

### 5) Verificar

```bash
docker compose logs -f
```

La aplicación estará corriendo internamente en el puerto `8000`, pero Traefik la expondrá al mundo de forma segura con HTTPS.
