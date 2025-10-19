FROM python:3.11-slim

# 1️⃣ Instalar dependencias del sistema y reemplazos modernos de fuentes
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    fonts-dejavu-core \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libpango-1.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    ca-certificates \
    wget \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2️⃣ Copiar archivos del proyecto
WORKDIR /app
COPY . /app

# 3️⃣ Instalar dependencias Python y Chromium
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# 4️⃣ Iniciar el servidor
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]
