# Usar uma imagem base oficial do Python
FROM python:3.11-slim

# Definir variáveis de ambiente para evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema operacional necessárias para o Playwright/Chromium
# (Baseado nas bibliotecas ausentes reportadas no aviso)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Dependências diretas do Playwright (incluindo as do aviso)
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libatspi2.0-0 libgbm1 libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libgtk-3-0 libgtk-4-1 libgraphene-1.0-0 libgstreamer-gl1.0-0 libgstreamer-plugins-bad1.0-0 libavif15 libenchant-2-2 libsecret-1-0 libmanette-0.2-0 libgles2 \
    # Limpar cache do apt
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copiar o arquivo de dependências do Python
COPY requirements.txt .

# Instalar dependências do Python e o navegador Playwright
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install

# Copiar o restante do código da aplicação
COPY . .

# Expor a porta que o Gunicorn usará (o Render define a variável PORT)
EXPOSE $PORT

# Comando para iniciar a aplicação com Gunicorn
# Escuta em 0.0.0.0 e usa a porta fornecida pelo Render
CMD ["gunicorn", "src.main:app", "--bind", "0.0.0.0:$PORT", "--workers", "4"]

