import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(APP_ROOT, ".env"))

EXIFTOOL_TIMEOUT = int(os.getenv("EXIFTOOL_TIMEOUT_SECONDS", "20"))

NON_WRITABLE_TAGS = frozenset({
    "SourceFile", "Directory", "FileName", "FileSize",
    "FileAccessDate", "FileInodeChangeDate",
    "FilePermissions", "FileType", "FileTypeExtension",
    "MIMEType", "ExifToolVersion", "ExifByteOrder",
    "EncodingProcess", "BitsPerSample", "ColorComponents",
    "YCbCrSubSampling", "ImageWidth", "ImageHeight",
    "ImageSize", "Megapixels",
})

# Tags that we want to allow editing even if ExifTool -listw doesn't explicitly 
# list them in a specific group, as they usually map to XMP or standard chunks.
LEME_COMMON_TAGS = {
    "Artist", "Author", "Title", "Description", "Subject", "Keywords", 
    "Copyright", "Creator", "Comment", "UserComment", "DateTimeOriginal",
    "CreateDate", "ModifyDate"
}

_WRITABLE_TAGS_CACHE = None

def get_writable_tags() -> set:
    global _WRITABLE_TAGS_CACHE
    if _WRITABLE_TAGS_CACHE is not None:
        return _WRITABLE_TAGS_CACHE
    
    try:
        path = _find_exiftool()
        result = subprocess.run([path, "-listw"], capture_output=True, text=True, check=True)
        # Output is a space-separated list of tags
        tags = set(result.stdout.split())
        _WRITABLE_TAGS_CACHE = tags
        return tags
    except Exception as e:
        logger.error(f"Error fetching writable tags: {e}")
        return set()

app = Flask(
    __name__,
    root_path=APP_ROOT,
    template_folder="templates",
    static_folder="static",
)

# Configuración de límite de tamaño (default 50MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _find_exiftool() -> str:
    path = shutil.which("exiftool")
    if not path:
        raise RuntimeError("No se encontró exiftool en el servidor.")
    return path


def run_exiftool(file_path: str) -> dict:
    # Adding -s to get Tag Names (IDs) instead of descriptions
    command = [_find_exiftool(), "-j", "-s", file_path]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            check=False, timeout=EXIFTOOL_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El análisis tardó demasiado.") from exc

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Error al ejecutar exiftool.")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Salida de exiftool inválida.") from exc

    return data[0] if data else {}


def write_exiftool(file_path: str, metadata: dict) -> dict:
    """Write metadata and verify. Returns {applied: [...], failed: [...], warnings: [...]}. Maryland"""
    tags_to_write = {
        k: v for k, v in metadata.items() if k not in NON_WRITABLE_TAGS
    }
    if not tags_to_write:
        return {
            "applied": [],
            "failed": list(metadata.keys()),
            "warnings": ["Todos los campos seleccionados son de solo lectura."]
        }

    command = [_find_exiftool(), "-overwrite_original"]
    for tag, value in tags_to_write.items():
        command.append(f"-{tag}={value}")
    command.append(file_path)

    warnings = []
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            check=False, timeout=EXIFTOOL_TIMEOUT,
        )
        if result.stderr:
            # Exiftool warnings usually start with "Warning: "
            for line in result.stderr.splitlines():
                if line.strip():
                    warnings.append(line.strip())
                    logger.debug("ExifTool write info: %s", line.strip())
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("La escritura de metadatos tardó demasiado.") from exc

    if result.returncode > 1:
        # Errors (return code > 1) are treated as fatal for that operation
        raise RuntimeError(result.stderr.strip() or "Error al escribir metadatos.")

    # Verify by re-reading metadata
    new_metadata = run_exiftool(file_path)
    applied = []
    failed = []
    for tag, requested_value in tags_to_write.items():
        actual = str(new_metadata.get(tag, ""))
        # Some tags might be partially modified or formatted differently, 
        # but let's stick to simple comparison or check if tag exists if it didn't before
        if actual == str(requested_value):
            applied.append(tag)
        else:
            # If it's not exactly the same, it might still have been written but formatted
            # but usually for the user, if it doesn't match what they put, it's a "failure" 
            # or at least worth noting.
            failed.append(tag)

    # Tags filtered by NON_WRITABLE_TAGS or not in writable list
    writable_list = get_writable_tags()
    for tag in metadata:
        # Check if the tag is writable. We check the base tag (without group prefix)
        base_tag = tag.split(":")[-1]
        is_writable = (
            base_tag in writable_list or 
            tag in writable_list or 
            base_tag in LEME_COMMON_TAGS
        )
        
        if (tag in NON_WRITABLE_TAGS or not is_writable) and tag not in failed:
            failed.append(tag)

    return {"applied": applied, "failed": failed, "warnings": warnings}


@app.after_request
def apply_security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; "
        "form-action 'self'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    upload = request.files.get("file")
    if not upload or upload.filename == "":
        return jsonify({"error": "Selecciona un archivo."}), 400

    safe_name = secure_filename(upload.filename)
    suffix = os.path.splitext(safe_name)[1] or ".bin"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            temp_path = f.name
        upload.save(temp_path)
        metadata = run_exiftool(temp_path)
        writable_tags = get_writable_tags()
        
        # Determine writability for each tag
        metadata_info = {}
        for k, v in metadata.items():
            base_tag = k.split(":")[-1]
            is_writable = (
                (base_tag in writable_tags or k in writable_tags or base_tag in LEME_COMMON_TAGS) 
                and k not in NON_WRITABLE_TAGS
            )
            
            metadata_info[k] = {
                "value": v,
                "writable": is_writable
            }

        # Inject common tags if they are missing
        for common_tag in LEME_COMMON_TAGS:
            if common_tag not in metadata_info:
                metadata_info[common_tag] = {
                    "value": "",
                    "writable": True
                }

        return jsonify({
            "metadata_info": metadata_info,
            "filename": safe_name
        })
    except Exception as exc:
        logger.exception("Error extracting metadata from '%s'", safe_name)
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


@app.route("/api/modify", methods=["POST"])
def api_modify():
    upload = request.files.get("file")
    if not upload or upload.filename == "":
        return jsonify({"error": "No se envió archivo."}), 400

    metadata_raw = request.form.get("metadata", "{}")
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError:
        return jsonify({"error": "Metadatos inválidos."}), 400

    safe_name = secure_filename(upload.filename)
    suffix = os.path.splitext(safe_name)[1] or ".bin"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            temp_path = f.name
        upload.save(temp_path)
        result = write_exiftool(temp_path, metadata)

        with open(temp_path, "rb") as f:
            file_data = f.read()

        file_b64 = base64.b64encode(file_data).decode("ascii")

        return jsonify({
            "file": file_b64,
            "filename": safe_name,
            "applied": result["applied"],
            "failed": result["failed"],
            "warnings": result.get("warnings", []),
        })
    except Exception as exc:
        logger.exception("Error modifying metadata for '%s'", safe_name)
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")), debug=False)
