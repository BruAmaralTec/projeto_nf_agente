import streamlit as st # Usado APENAS para type hint UploadFile
import os
import uuid
import shutil # Para manipulação de arquivos (copiar/mover/remover)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import uvicorn # Para rodar o servidor (embora não seja chamado diretamente no código)
from typing import Dict, Any, Optional

# --- MUDANÇA AQUI: Importação adicionada ---
from langchain_core.messages import HumanMessage
# --- FIM DA MUDANÇA ---

# Importa o CÉREBRO do nosso agente LangGraph
from workflows.graph import app as langgraph_app
# Importa o "molde" de dados Pydantic
from tools.extracao import DadosNotaFiscal

# --- Diretórios ---
API_UPLOAD_DIR = "api_uploads"
os.makedirs(API_UPLOAD_DIR, exist_ok=True)

# --- Inicializa o aplicativo FastAPI ---
api = FastAPI(
    title="Meta Singularity NF Extractor API",
    description="API para extrair dados de notas fiscais usando um agente LangGraph.",
    version="1.0.0"
)

# --- Endpoint de Teste (Raiz) ---
@api.get("/")
async def read_root():
    """Endpoint inicial para verificar se a API está no ar."""
    return {"message": "API Meta Singularity NF Extractor está funcionando!"}

# --- Endpoint Principal de Processamento ---
@api.post("/processar_nf/",
          summary="Processa um arquivo de Nota Fiscal",
          response_description="JSON contendo os dados extraídos da nota fiscal")
async def processar_nota_fiscal(
    file: UploadFile = File(..., description="Arquivo da Nota Fiscal (.pdf, .xml, .html, .png, .jpg)"),
    mode: str = Form(..., description="Modo de operação: 'single' ou 'accumulated'")
) -> JSONResponse:
    """
    Recebe um arquivo de nota fiscal e o modo de operação,
    processa usando o agente LangGraph e retorna os dados extraídos em JSON.
    """
    print(f"Recebida requisição para processar '{file.filename}' no modo '{mode}'")

    if mode not in ["single", "accumulated"]:
        raise HTTPException(status_code=400, detail="Modo inválido. Use 'single' ou 'accumulated'.")

    # --- Salvar Arquivo Temporariamente ---
    temp_file_path = os.path.join(API_UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"Arquivo salvo temporariamente em: {temp_file_path}")
    except Exception as e:
        print(f"Erro ao salvar arquivo temporário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {e}")
    finally:
        await file.close()

    # --- Preparar e Chamar o Agente LangGraph ---
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    prompt_tecnico = f"Processar via API: {temp_file_path}"

    estado_inicial = {
        "messages": [HumanMessage(content=prompt_tecnico)], # Agora HumanMessage está definido
        "file_path": temp_file_path,
        "excel_file_path": None,
        "app_mode": mode,
        "extracted_data": None
    }

    try:
        print(f"Invocando agente LangGraph (Thread ID: {thread_id})...")
        final_state = langgraph_app.invoke(estado_inicial, config=config)
        print("Agente LangGraph concluiu.")

        dados_extraidos = final_state.get("extracted_data")
        excel_path = final_state.get("excel_file_path")

        if dados_extraidos:
             print(f"Dados extraídos com sucesso. Excel salvo em: {excel_path}")
             return JSONResponse(content=dados_extraidos, status_code=200)
        else:
             last_message = final_state.get("messages", [])[-1]
             error_detail = f"Agente concluiu, mas não retornou dados extraídos. Última mensagem: {getattr(last_message, 'content', 'N/A')}"
             print(error_detail)
             raise HTTPException(status_code=500, detail=error_detail)

    except Exception as e:
        print(f"Erro durante a execução do agente LangGraph: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor ao processar a nota: {e}")

    finally:
        # --- Limpeza do Arquivo Temporário ---
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print(f"Arquivo temporário removido: {temp_file_path}")
        except OSError as e:
            print(f"Erro ao remover arquivo temporário {temp_file_path}: {e}")

# --- Instrução para Rodar (não faz parte do código da API em si) ---
if __name__ == "__main__":
    print("\n--- Para rodar a API localmente, use o comando no terminal: ---")
    print("uvicorn api:api --reload")
    print("---------------------------------------------------------------\n")