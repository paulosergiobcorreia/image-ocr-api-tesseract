from fastapi import FastAPI, UploadFile, File, HTTPException
import pytesseract
import cv2
import numpy as np
from PIL import Image
import os
import uuid
from pathlib import Path
import psycopg2
from psycopg2 import sql

app = FastAPI()

# Configuração do banco de dados (usando as variáveis de ambiente do Render)
try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "image_ocr_db"),
        user=os.getenv("DB_USER", "image_ocr_db_user"),
        password=os.getenv("DB_PASSWORD", "MD3EfkfWD1gtStebg3TpBBK34Q1bMp26"),
        host=os.getenv("DB_HOST", "dpg-d04m6195pdvs73a7ojjg-a.oregon-postgres.render.com"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()
except Exception as e:
    raise Exception(f"Erro ao conectar ao banco de dados: {str(e)}")

# Cria a tabela se não existir
cursor.execute("""
    CREATE TABLE IF NOT EXISTS ocr_data (
        id VARCHAR(36) PRIMARY KEY,
        extracted_text TEXT,
        image_path VARCHAR(255)
    );
""")
conn.commit()

# Função para pré-processar a imagem
def preprocess_image(image_path):
    # Carrega a imagem com OpenCV
    img = cv2.imread(image_path)
    
    # Converte para escala de cinza
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Aumenta o contraste
    alpha = 1.5  # Fator de contraste (1.0 = sem alteração, >1 aumenta)
    beta = 0     # Brilho (0 = sem alteração)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    
    # Aplica limiar (threshold) para binarizar a imagem
    _, binary = cv2.threshold(adjusted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Salva a imagem processada temporariamente
    processed_path = image_path.replace(".png", "_processed.png")
    cv2.imwrite(processed_path, binary)
    
    return processed_path

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # Verifica se o arquivo é uma imagem
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem")

    # Cria o diretório "uploads" se não existir
    Path("uploads").mkdir(exist_ok=True)
    
    # Salva a imagem original
    file_id = str(uuid.uuid4())
    file_path = f"uploads/{file_id}.png"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Pré-processa a imagem
    processed_path = preprocess_image(file_path)

    # Extrai texto com o Tesseract, usando parâmetros
    image = Image.open(processed_path)
    custom_config = r'--oem 3 --psm 6'  # OEM 3 (padrão), PSM 6 (texto em bloco único)
    extracted_text = pytesseract.image_to_string(image, config=custom_config)

    # Remove a imagem processada temporária
    os.remove(processed_path)

    # Salva no banco de dados
    try:
        cursor.execute(
            sql.SQL("INSERT INTO ocr_data (id, extracted_text, image_path) VALUES (%s, %s, %s)"),
            (file_id, extracted_text, file_path)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {str(e)}")

    return {
        "extracted_text": extracted_text,
        "id": file_id,
        "image_path": file_path
    }

@app.get("/data")
async def get_all_data():
    try:
        cursor.execute("SELECT id, extracted_text, image_path FROM ocr_data")
        rows = cursor.fetchall()
        return [
            {"id": row[0], "extracted_text": row[1], "image_path": row[2]}
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar o banco: {str(e)}")

@app.get("/data/{item_id}")
async def get_data_by_id(item_id: str):
    try:
        cursor.execute(
            sql.SQL("SELECT id, extracted_text, image_path FROM ocr_data WHERE id = %s"),
            (item_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        return {
            "id": row[0],
            "extracted_text": row[1],
            "image_path": row[2]
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar o banco: {str(e)}")

# Fecha a conexão com o banco ao encerrar a API
@app.on_event("shutdown")
def shutdown_event():
    cursor.close()
    conn.close()
