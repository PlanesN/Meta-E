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

Dado que en tu servidor ya cuentas con Traefik, Matrix y Docker, el proceso es mucho más ágil pues no requieres configurar Nginx ni puertos.

### 1) Preparar y subir el proyecto al servidor

Antes de subirlo, crea un archivo `.zip` de tu proyecto evitando copiar entornos virtuales:

```bash
# Comprime la carpeta omitiendo git y venv
zip -r meta-e.zip Meta-E/ -x "Meta-E/venv/*" "Meta-E/.*" "Meta-E/.git/*" "Meta-E/__pycache__/*"
```

Súbelo a tu servidor Ubuntu usando `scp`:

```bash
scp meta-e.zip usuario@IP_DEL_SERVIDOR:/home/usuario/
```

### 2) Extraer en el servidor

Conéctate por SSH a tu servidor y descomprime el archivo:

```bash
ssh usuario@IP_DEL_SERVIDOR
unzip meta-e.zip -d meta-e
cd meta-e
```

### 3) Ajustar `docker-compose.yml`

Abre tu archivo y ajústalo para que se integre con tu Traefik:

```bash
nano docker-compose.yml
```

Debes hacer que coincida exactamente con tu servidor:
1. **Red de Traefik:** Busca `traefik-net` bajo la directiva `networks:` (al fondo del archivo) y reemplázalo por el **mismo nombre de la red** donde corren Traefik y Matrix (ej. `proxy`, `web`, `matrix_default`, etc).
2. **Dominio:** En `traefik.http.routers.metadata.rule`, cambia ``Host(`meta.mexicosadecv.com.mx`)`` por tu subdominio real.
3. **Certresolver SSL:** En la etiqueta `certresolver=myresolver`, cambia `myresolver` por el nombre de tu resolver configurado en el Traefik de tu Ubuntu (normalmente es `letsencrypt` o `le`).

Guarda y cierra (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 4) Configurar variables de entorno locales

Asegúrate de preparar tu archivo `.env` para que defina los tiempos de espera y vinculaciones de puerto:

```bash
cp .env.example .env
```
(Edita `.env` con `nano .env` si requieres modificar credenciales internas de la API en el futuro).

### 5) Construir y levantar el contenedor

Ejecuta Compose para que construya la imagen (con las dependencias de ExifTool de Ubuntu/Debian) y registre el servicio en Traefik:

```bash
docker compose up -d --build
```

### 6) Verificar logs de Gunicorn

Monitorea que la app arranque sin errores de dependencias y que Traefik la haya reconocido:

```bash
docker compose logs -f
```
*(Para salir pulsa `Ctrl+C`)*. 

¡Listo! Ingresa a tu subdominio en el navegador. Traefik enrutará todo al puerto interno `8000` del contenedor.
