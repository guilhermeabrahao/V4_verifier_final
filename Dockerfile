# Usar uma imagem base Python mais completa (Debian Bullseye)
FROM python:3.11-bullseye

# Definir variáveis de ambiente
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema operacional listadas como ausentes
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Bibliotecas listadas no log de erro do Playwright (corrigido)
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libexpat1 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    # Limpar cache do apt
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar o arquivo de dependências
COPY requirements.txt .

# Instalar dependências do Python e o navegador Playwright (sem install-deps agora)
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# Copiar o restante do código
COPY . .

# Comando para iniciar a aplicação (mantendo a correção para $PORT)
CMD sh -c "gunicorn src.main:app --bind 0.0.0.0:$PORT --workers 4"

