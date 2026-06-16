FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["/bin/sh", "-c", "python script.py || (echo 'O script falhou, mantendo vivo por 10 min' && sleep 600)"]