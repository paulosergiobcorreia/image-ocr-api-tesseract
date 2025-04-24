FROM python:3.9
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-por
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "api:app"]
