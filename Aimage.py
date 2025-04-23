from flask import Flask, request, jsonify
import pytesseract
from PIL import Image
import psycopg2
from psycopg2 import pool
import os
import uuid

app = Flask(__name__)

# Configuração do banco de dados PostgreSQL
db_pool = None

def init_db_pool():
    global db_pool
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20,
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

# Inicializa o banco de dados e cria a tabela
def init_db():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS extracted_data (
                         id TEXT PRIMARY KEY,
                         extracted_text TEXT,
                         image_path TEXT
                         )''')
            conn.commit()
    finally:
        db_pool.putconn(conn)

# Inicializa o pool e o banco
init_db_pool()
init_db()

# Endpoint para upload de imagem
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem enviada'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    try:
        # Salva a imagem temporariamente
        image_path = f"uploads/{uuid.uuid4()}.png"
        os.makedirs('uploads', exist_ok=True)
        file.save(image_path)

        # Extrai texto usando Tesseract
        image = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(image, lang='por')  # Configurado para português

        # Gera um ID único para o registro
        record_id = str(uuid.uuid4())

        # Salva os dados no banco de dados
        conn = db_pool.getconn()
        try:
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO extracted_data (id, extracted_text, image_path) VALUES (%s, %s, %s)",
                    (record_id, extracted_text, image_path)
                )
                conn.commit()
        finally:
            db_pool.putconn(conn)

        # Retorna o texto extraído e o ID do registro
        return jsonify({
            'id': record_id,
            'extracted_text': extracted_text,
            'image_path': image_path
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint para consultar dados por ID
@app.route('/data/<id>', methods=['GET'])
def get_data(id):
    try:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as c:
                c.execute("SELECT * FROM extracted_data WHERE id = %s", (id,))
                data = c.fetchone()
                if data:
                    return jsonify({
                        'id': data[0],
                        'extracted_text': data[1],
                        'image_path': data[2]
                    }), 200
                else:
                    return jsonify({'error': 'Registro não encontrado'}), 404
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint para listar todos os registros
@app.route('/data', methods=['GET'])
def list_data():
    try:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as c:
                c.execute("SELECT * FROM extracted_data")
                rows = c.fetchall()
                data = [{'id': row[0], 'extracted_text': row[1], 'image_path': row[2]} for row in rows]
                return jsonify(data), 200
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))