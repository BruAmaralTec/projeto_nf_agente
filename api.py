import streamlit as st # Import st para usar cache se necessário
import os
import uuid
import shutil # Para lidar com arquivos temporários de forma segura
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

# Importa o nosso cérebro LangGraph compilado
from workflows.graph import app as langgraph_app 
from langchain_core.messages import HumanMessage

# Importa o nosso "molde" de dados Pydantic
from tools.extracao import DadosNotaFiscal 

# --- Configuração ---
# Diretórios temporários para a API (separados do Streamlit para clareza)
API_UPLOAD_DIR = "api_temp_uploads"
os.makedirs(API_UPLOAD_DIR, exist_ok=True)

# --- Instância do FastAPI ---
# Define metadados básicos para a documentação automática da API
api = FastAPI(
    title="Meta Singularity - API Agente Extrator NF",
    description="API para processar Notas Fiscais (PDF, XML, Imagem, HTML) usando um agente LangGraph.",
    version="1.0.0",
)

# --- FUNÇÃO PRINCIPAL DE PROCESSAMENTO (Pode ser otimizada com cache) ---
# @st.cache_data # Descomente se quiser cache baseado nos bytes do arquivo
def process_fiscal_note(file_path: str, app_mode: str) -> Optional[Dict[str, Any]]:
    """
    Função reutilizável que invoca o agente LangGraph.
    Recebe o caminho do arquivo e o modo, retorna o dicionário de dados extraídos.
    """
    thread_id = str(uuid.uuid4()) # Novo ID para cada requisição API (isolamento)
    config = {"configurable": {"thread_id": thread_id}}
    
    # Prepara o estado inicial para o grafo
    # Usamos um prompt técnico simples para a API
    prompt_tecnico = f"API Request: Processar arquivo em {file_path} no modo {app_mode}"
    estado_inicial = {
        "messages": [HumanMessage(content=prompt_tecnico)],
        "file_path": file_path,
        "excel_file_path": None,
        "app_mode": app_mode, # Passa o modo recebido pela API
        "extracted_data": None
    }

    try:
        print(f"API: Iniciando processamento do agente para {file_path} (Thread: {thread_id})")
        # Invoca o agente LangGraph
        final_state = langgraph_app.invoke(estado_inicial, config=config)
        print(f"API: Processamento do agente concluído (Thread: {thread_id})")
        
        # Recupera os dados extraídos do estado final
        extracted_data = final_state.get("extracted_data")
        
        # Opcional: Recupera o caminho do Excel salvo, se precisar retornar também
        excel_path = final_state.get("excel_file_path")
        if excel_path:
             print(f"API: Arquivo Excel gerado em: {excel_path}")
             # Poderíamos adicionar 'excel_path' ao dict retornado se a API precisar disso

        return extracted_data

    except Exception as e:
        print(f"API: Erro durante a invocação do agente (Thread: {thread_id}): {e}")
        # Retorna None ou levanta uma exceção específica da API
        return None

# --- Background Task para Limpeza ---
def cleanup_temp_file(path: str):
    """Função para ser executada em segundo plano para deletar o arquivo temporário."""
    try:
        os.remove(path)
        print(f"API Cleanup: Arquivo temporário removido: {path}")
    except OSError as e:
        print(f"API Cleanup Error: Falha ao remover {path}: {e}")

# --- ENDPOINT DA API ---
@api.post(
    "/processar_nf/",
    response_model=Optional[DadosNotaFiscal], # Define o formato da resposta JSON usando nosso Pydantic!
    summary="Processa um arquivo de Nota Fiscal",
    description="Recebe um arquivo (pdf, xml, html, png, jpg) e o modo ('single' ou 'accumulated'). Retorna os dados extraídos em JSON.",
    tags=["Notas Fiscais"] # Agrupa na documentação
)
async def processar_nota_fiscal(
    background_tasks: BackgroundTasks, # Para limpeza em segundo plano
    file: UploadFile = File(..., description="O arquivo da nota fiscal a ser processado."),
    app_mode: str = Form(
        ..., 
        description="Modo de operação: 'single' (arquivo único) ou 'accumulated' (compilado).",
        pattern="^(single|accumulated)$" # Valida a entrada
    )
):
    """
    Endpoint principal para processar notas fiscais.
    
    - **file**: O arquivo da nota fiscal.
    - **app_mode**: 'single' ou 'accumulated'.
    """
    # 1. Salvar o arquivo recebido temporariamente
    try:
        # Cria um caminho seguro para o arquivo temporário
        temp_file_path = os.path.join(API_UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
        
        # Salva o conteúdo do upload no disco
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"API: Arquivo recebido e salvo temporariamente em: {temp_file_path}")
        
        # Agenda a limpeza do arquivo para DEPOIS que a resposta for enviada
        background_tasks.add_task(cleanup_temp_file, temp_file_path)

    except Exception as e:
        print(f"API Error: Falha ao salvar arquivo temporário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar o arquivo: {e}")
    finally:
        # Garante que o arquivo seja fechado pelo FastAPI
        await file.close()

    # 2. Chamar a função de processamento com o agente
    extracted_data = process_fiscal_note(temp_file_path, app_mode)

    # 3. Tratar o resultado e retornar a resposta JSON
    if extracted_data is None:
        # Se process_fiscal_note retornou None, significa que houve um erro interno do agente
        raise HTTPException(status_code=500, detail="Erro interno do agente ao processar o arquivo.")
    
    if not extracted_data:
        # Se o dicionário está vazio (agente não extraiu nada)
        # Retorna um JSON vazio com status 200 OK ou um 404 Not Found? 
        # Vamos retornar 200 OK com um objeto vazio, indicando sucesso no processo, mas sem dados.
         print("API: Agente processou, mas não extraiu dados.")
         return JSONResponse(content={}, status_code=200)

    print(f"API: Dados extraídos com sucesso. Retornando JSON.")
    # FastAPI automaticamente converte o dicionário em JSON
    # e valida se ele corresponde ao response_model (DadosNotaFiscal)
    return extracted_data