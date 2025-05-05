# Usar uma imagem base oficial do Python
FROM python:3.11-slim

# Definir variáveis de ambiente para evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema operacional necessárias para o Playwright/Chromium
# Incluindo as do aviso e usando o comando recomendado pelo Playwright
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copiar o arquivo de dependências do Python
COPY requirements.txt .

# Instalar dependências do Python, o navegador Playwright e suas dependências de sistema
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && playwright install-deps chromium --dry-run \
    && playwright install-deps chromium

# Copiar o restante do código da aplicação
COPY . .

# Comando para iniciar a aplicação com Gunicorn
# Usa sh -c para permitir a expansão da variável $PORT
# Escuta em 0.0.0.0 e usa a porta fornecida pelo Render
CMD sh -c "gunicorn src.main:app --bind 0.0.0.0:$PORT --workers 4"

