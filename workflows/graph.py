import os
import pandas as pd
from typing import TypedDict, Annotated, List, Union, Optional, Dict, Any # <-- Adicionado Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import operator

# --- 1. Importar NOSSAS FERRAMENTAS ---
from tools.extracao import (
    # Ferramentas que o LLM VÊ
    extrair_dados_xml, 
    extrair_texto_imagem, 
    extrair_texto_pdf, 
    extrair_texto_html,
    salvar_dados_nota, 
    
    # Funções de lógica interna que o LLM NÃO VÊ
    salvar_dados_em_excel,
    acumular_dados_em_excel,
    
    DadosNotaFiscal 
)

# Carregar as variáveis de ambiente (nosso .env)
from dotenv import load_dotenv
load_dotenv()

# --- 2. Definir as Ferramentas para o Agente ---
tools = [
    extrair_dados_xml, 
    extrair_texto_imagem, 
    extrair_texto_pdf, 
    extrair_texto_html,
    salvar_dados_nota 
]

# --- 3. Definir o Modelo (LLM) ---
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
model_with_tools = model.bind_tools(tools)

# --- 4. Definir as Instruções (System Prompt) ---
system_prompt = """
Você é um assistente especialista em processamento de notas fiscais brasileiras.
Sua missão é seguir um processo de duas etapas:

Etapa 1: Extração de Dados Brutos.
- O usuário fornecerá o caminho para um arquivo (XML, PDF, HTML, PNG, JPG).
- Você DEVE escolher a ferramenta de extração de dados CORRETA com base no tipo de arquivo.
- Você receberá o texto bruto extraído pela ferramenta.

Etapa 2: Formatação e Salvamento.
- Após receber o texto bruto, analise-o CUIDADOSAMENTE.
- Você DEVE extrair todos os campos a seguir que conseguir encontrar. Se um campo não for encontrado, deixe-o nulo.
- CAMPOS PARA EXTRAIR:
  - chave_acesso
  - numero_nf
  - data_emissao
  - cnpj_emitente
  - nome_emitente
  - endereco_emitente
  - municipio_emitente
  - cnpj_cpf_destinatario
  - nome_destinatario
  - endereco_destinatario
  - municipio_destinatario
  - valor_total (use o valor final/líquido)
  - base_calculo
  - valor_iss
  - valor_icms
  - discriminacao_servicos (se for uma nota de serviço)
- Use o seu conhecimento para limpar os dados.
- Quando tiver todos os dados estruturados, você DEVE chamar a ferramenta 'salvar_dados_nota'.
"""

# --- 5. Definir o "Estado" do Agente (A Memória) ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    file_path: str
    excel_file_path: Optional[str] = None
    app_mode: str 
    # --- MUDANÇA CRUCIAL (v3.7): Campo para guardar os dados extraídos ---
    extracted_data: Optional[Dict[str, Any]] = None 

# --- 6. Definir os "Nós" do Gráfico (As Etapas) ---

def call_model(state: AgentState):
    """Chama o LLM para decidir o próximo passo."""
    print("--- Nó: call_model (Agente) ---")
    messages = state["messages"]
    
    if len(messages) == 1:
        messages_with_prompt = [ HumanMessage(content=system_prompt), messages[0] ]
    else:
        messages_with_prompt = messages

    response = model_with_tools.invoke(messages_with_prompt)
    return {"messages": [response]}

# NÓ ATUALIZADO: call_tools
def call_tools(state: AgentState):
    """Executa as ferramentas que o agente decidiu usar E faz o roteamento lógico."""
    print("--- Nó: call_tools (Ação) ---")
    last_message = state["messages"][-1]
    
    if not last_message.tool_calls:
        print("Agente não chamou ferramentas. Fim do passo.")
        return {}

    tool_messages = []
    # Pega os valores atuais do estado
    excel_path = state.get("excel_file_path") 
    app_mode = state["app_mode"] 
    extracted_data_dict = state.get("extracted_data") # Pega o valor atual

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        print(f"Agente chamou ferramenta: {tool_name}")
        args = tool_call["args"]
        
        try:
            resultado_msg_para_agente = ""
            
            # Lógica de Roteamento (MODIFICADA para capturar dados)
            if tool_name == "salvar_dados_nota":
                print(f"Roteamento de salvamento. Modo atual: {app_mode}")
                dados_pydantic = DadosNotaFiscal(**args['dados_nota'])
                
                # --- MUDANÇA CRUCIAL (v3.7): Captura a tupla ---
                if app_mode == 'single':
                    resultado_tupla = salvar_dados_em_excel(dados_pydantic) 
                else: # 'accumulated'
                    resultado_tupla = acumular_dados_em_excel(dados_pydantic)
                
                # Desempacota a tupla
                resultado_msg, dados_retornados_dict = resultado_tupla
                
                # Prepara a resposta e atualiza o estado
                if not str(resultado_msg).startswith("Erro"):
                    excel_path = str(resultado_msg) # Atualiza o caminho do Excel
                    extracted_data_dict = dados_retornados_dict # Atualiza os dados extraídos
                    if app_mode == 'single':
                         resultado_msg_para_agente = f"Arquivo salvo com sucesso em: {excel_path}"
                    else:
                         resultado_msg_para_agente = f"Dados ACUMULADOS com sucesso em: {excel_path}"
                else:
                    resultado_msg_para_agente = str(resultado_msg) # Passa a msg de erro
                    # Não atualiza extracted_data_dict em caso de erro de salvamento
            
            # Ferramentas de extração (lógica normal)
            elif tool_name in ["extrair_dados_xml", "extrair_texto_imagem", "extrair_texto_pdf", "extrair_texto_html"]:
                if tool_name == "extrair_dados_xml": args = {"caminho_do_arquivo_xml": state["file_path"]}
                if tool_name == "extrair_texto_imagem": args = {"caminho_do_arquivo_imagem": state["file_path"]}
                if tool_name == "extrair_texto_pdf": args = {"caminho_do_arquivo_pdf": state["file_path"]}
                if tool_name == "extrair_texto_html": args = {"caminho_do_arquivo_html": state["file_path"]}
                
                ferramenta = globals()[tool_name]
                resultado = ferramenta.func(**args)
                resultado_msg_para_agente = str(resultado)
            
            else:
                resultado_msg_para_agente = f"Erro: Ferramenta '{tool_name}' desconhecida."

            tool_messages.append(ToolMessage(content=resultado_msg_para_agente, tool_call_id=tool_call["id"]))

        except Exception as e:
            print(f"Erro ao executar ferramenta {tool_name}: {e}")
            tool_messages.append(ToolMessage(content=f"Erro: {e}", tool_call_id=tool_call["id"]))

    # --- MUDANÇA CRUCIAL (v3.7): Retorna o novo campo do estado ---
    return {
        "messages": tool_messages, 
        "excel_file_path": excel_path, 
        "extracted_data": extracted_data_dict # Retorna os dados extraídos para o estado
    }


# --- 7. Definir a "Lógica" (Sem mudanças) ---
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return END

# --- 8. Montar e Compilar o Gráfico (Sem mudanças) ---
print("Compilando o workflow do agente (v3.7 - Retorna Dados)...")
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("action", call_tools)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"action": "action", END: END})
workflow.add_edge("action", "agent")
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
print("Workflow compilado com sucesso!")