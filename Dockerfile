FROM python:3.9-slim

# Install system dependencies (exiftool)
RUN apt-get update && apt-get install -y \
    libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8000

# Start Gunicorn directly
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--timeout", "300", "app:app"]
