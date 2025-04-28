import os
     import uuid
     from pathlib import Path
     import psycopg2
     from psycopg2 import sql
     import cv2
     from PIL import Image
     import pytesseract
     from fastapi import FastAPI, File, UploadFile, HTTPException

     app = FastAPI()

     # Configuração do banco de dados PostgreSQL (será inicializado sob demanda)
     DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:114723@localhost:5432/ocr_db")

     def get_db_connection():
         try:
             conn = psycopg2.connect(DATABASE_URL)
             cursor = conn.cursor()
             # Criação da tabela no banco de dados, se não existir
             cursor.execute("""
                 CREATE TABLE IF NOT EXISTS ocr_data (
                     id TEXT PRIMARY KEY,
                     extracted_text TEXT,
                     image_path TEXT
                 );
             """)
             conn.commit()
             return conn, cursor
         except Exception as e:
             raise HTTPException(status_code=500, detail=f"Erro ao conectar ao banco: {str(e)}")

     def preprocess_image(image_path):
         # Carrega a imagem
         image = cv2.imread(image_path)
         
         # Converte para escala de cinza
         gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
         
         # Aplica um desfoque para reduzir ruído
         blurred = cv2.GaussianBlur(gray, (5, 5), 0)
         
         # Aplica limiarização adaptativa para lidar com variações de cor
         thresh = cv2.adaptiveThreshold(
             blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
         )
         
         # Inverte a imagem para que o texto seja preto e o fundo branco
         thresh = cv2.bitwise_not(thresh)
         
         # Salva a imagem processada
         processed_path = image_path.replace(".png", "_processed.png")
         cv2.imwrite(processed_path, thresh)
         
         return processed_path

     @app.get("/")
     async def root():
         return {"message": "Bem-vindo à API de OCR com Tesseract!"}

     @app.get("/data")
     async def get_data():
         conn, cursor = get_db_connection()
         try:
             cursor.execute("SELECT * FROM ocr_data")
             rows = cursor.fetchall()
             return [{"id": row[0], "extracted_text": row[1], "image_path": row[2]} for row in rows]
         finally:
             cursor.close()
             conn.close()

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
         image_processed = Image.open(processed_path)
         custom_config = r'--oem 3 --psm 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:().% -'
         extracted_text = pytesseract.image_to_string(image_processed, config=custom_config)

         # Remove a imagem processada temporária
         os.remove(processed_path)

         # Salva no banco de dados
         conn, cursor = get_db_connection()
         try:
             cursor.execute(
                 sql.SQL("INSERT INTO ocr_data (id, extracted_text, image_path) VALUES (%s, %s, %s)"),
                 (file_id, extracted_text, file_path)
             )
             conn.commit()
         except Exception as e:
             conn.rollback()
             raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {str(e)}")
         finally:
             cursor.close()
             conn.close()

         return {
             "extracted_text": extracted_text,
             "id": file_id,
             "image_path": file_path
         }
