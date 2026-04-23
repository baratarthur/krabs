FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 5001

ENV FLASK_APP=app.py

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5002", "main:app"]