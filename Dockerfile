# Usa a imagem base do Python 3.9
FROM python:3.9-slim

# Instala dependências do sistema, incluindo o Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia primeiro o requirements.txt para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto
COPY . .

# Define a variável de ambiente para o Gunicorn encontrar o app
ENV PYTHONPATH=/app

# Verifica se o Tesseract está instalado
RUN tesseract --version

# Verifica se o app.py pode ser importado
RUN python -c "import app"

# Comando para iniciar a aplicação
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:10000", "app:app"]
