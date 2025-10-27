# --- Estágio 1: Base e Dependências do Sistema ---

# Usamos uma imagem Python oficial baseada no Debian 12 ('bookworm'), versão 'slim' para economizar espaço.
FROM python:3.11-slim-bookworm AS base

# Define variáveis de ambiente úteis
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    # Define o diretório de trabalho padrão
    WORKDIR=/app

# Instala dependências do sistema operacional necessárias
# (Tesseract, Poppler, dependência do OpenCV, e ferramentas básicas)
RUN apt-get update && \
    apt-get install -y --no-install-recommend \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libgl1-mesa-glx \
    curl \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# --- Estágio 2: Dependências Python ---

# Copia APENAS o arquivo de requisitos para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python usando pip
RUN pip install --no-cache-dir -r requirements.txt

# --- Estágio 3: Código da Aplicação ---

# Copia todo o resto do código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Uvicorn usará (AGORA É DINÂMICO via $PORT)
# EXPOSE 8000 # Não precisamos mais fixar aqui

# --- MUDANÇA CRUCIAL AQUI ---
# Define o comando que será executado quando o container iniciar
# Roda a API FastAPI usando Uvicorn
# --host 0.0.0.0 : Permite que a API seja acessível de fora do container
# --port $PORT : USA A VARIÁVEL DE AMBIENTE FORNECIDA PELA PLATAFORMA (ex: Render)
# api:api : No arquivo 'api.py', encontre o objeto 'api'
CMD ["uvicorn", "api:api", "--host", "0.0.0.0", "--port", "$PORT"]
# --- FIM DA MUDANÇA ---