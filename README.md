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

## Despliegue con Docker y Traefik en Ubuntu Server

### Consideraciones previas
1. **Pausar Nginx/Apache:** Si tenías Nginx u otro servidor web, detenlo para liberar los puertos 80 y 443 a Traefik.
   ```bash
   sudo systemctl stop nginx
   sudo systemctl disable nginx
   ```
2. **Firewall (UFW):** Asegúrate de tener los puertos 80 y 443 abiertos para Traefik.
   ```bash
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw reload
   ```
3. **Red de Docker:** El contenedor debe estar en la misma red de Docker que tu Traefik principal (`traefik-net` en el ejemplo).

### 1) Subir proyecto al servidor

Ejemplo en `/opt/metadata-extractor`.

```bash
sudo mkdir -p /opt/metadata-extractor
sudo chown -R $USER:$USER /opt/metadata-extractor
cd /opt/metadata-extractor
# copiar o clonar tu proyecto aquí
```

### 2) Configurar variables y entorno
Copia el archivo de ejemplo:
```bash
cd /opt/metadata-extractor
cp .env.example .env
```
Recuerda ajustar en tu `docker-compose.yml`:
- El dominio: `Host(\`threema.mexicosadecv.com.mx\`)`
- El resolver TLS: `certresolver=myresolver`
- La red (`traefik-net`) según cómo se llame la red de tu Traefik principal.

### 3) Levantar el contenedor

Usa Docker Compose para construir y levantar el servicio:
```bash
docker compose up -d --build
```

### 4) Verificar logs

Puedes monitorear que Gunicorn y ExifTool estén respondiendo correctamente:
```bash
docker compose logs -f
```

## Notas

- No subas `.env` al repositorio.
- La carpeta `deploy/` original (nginx y systemd) ya no es necesaria y puedes eliminarla con seguridad.
