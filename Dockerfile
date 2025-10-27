# --- Estágio 1: Base e Dependências do Sistema ---

# Usamos uma imagem Python oficial baseada no Debian 12 ('bookworm'), versão 'slim' para economizar espaço.
FROM python:3.11-slim-bookworm AS base

# Define variáveis de ambiente úteis
ENV PYTHONUNBUFFERED=1 \
    # Configura pip para não guardar cache (mantém a imagem menor)
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # Configura Poetry (se usássemos), mas bom ter como referência
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    # Define o diretório de trabalho padrão
    WORKDIR=/app

# Instala dependências do sistema operacional necessárias
# (Tesseract, Poppler, dependência do OpenCV, e ferramentas básicas)
# Equivalente ao nosso packages.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libgl1-mesa-glx \
    curl \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# --- Estágio 2: Dependências Python ---

# Copia APENAS o arquivo de requisitos para aproveitar o cache do Docker
# Se requirements.txt não mudar, o Docker não reinstalará tudo
COPY requirements.txt .

# Instala as dependências Python usando pip (ou uv se preferir)
# Usar --no-cache-dir é importante para manter a imagem pequena
RUN pip install --no-cache-dir -r requirements.txt

# --- Estágio 3: Código da Aplicação ---

# Copia todo o resto do código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Uvicorn usará (padrão 8000)
EXPOSE 8000

# Define o comando que será executado quando o container iniciar
# Roda a API FastAPI usando Uvicorn
# --host 0.0.0.0 : Permite que a API seja acessível de fora do container
# --port 8000 : Porta definida acima
# api:api : No arquivo 'api.py', encontre o objeto 'api'
CMD ["uvicorn", "api:api", "--host", "0.0.0.0", "--port", "8000"]