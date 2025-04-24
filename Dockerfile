# Usa uma imagem base com Python
FROM python:3.9-slim

# Instala dependências do sistema para Tesseract e OpenCV
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Cria o diretório para uploads
RUN mkdir -p uploads

# Define o comando para iniciar a API usando gunicorn com worker uvicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "app:app"]
