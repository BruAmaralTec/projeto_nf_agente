import os
import pandas as pd
from typing import TypedDict, Annotated, List, Union, Optional
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
    salvar_dados_nota,  # A única ferramenta de salvar que o LLM vê
    
    # Funções de lógica interna que o LLM NÃO VÊ
    salvar_dados_em_excel,
    acumular_dados_em_excel,
    
    DadosNotaFiscal # O "molde" expandido
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
# --- MUDANÇA CRUCIAL: O PROMPT FOI ATUALIZADO ---
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
  - valor_total (use o valor final/líquido, ex: 'Valor a pagar' ou 'Valor Total do Serviço')
  - base_calculo
  - valor_iss
  - valor_icms
  - discriminacao_servicos (se for uma nota de serviço)
- Use o seu conhecimento para limpar os dados (ex: remover 'R$', manter apenas números em CNPJs, formatar valores como 1234.56).
- Quando tiver todos os dados estruturados, você DEVE chamar a ferramenta 'salvar_dados_nota'.
"""

# --- 5. Definir o "Estado" do Agente (Sem mudanças) ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    file_path: str
    excel_file_path: Optional[str] = None
    app_mode: str 

# --- 6. Definir os "Nós" do Gráfico (Sem mudanças) ---

def call_model(state: AgentState):
    """Chama o LLM para decidir o próximo passo."""
    print("--- Nó: call_model (Agente) ---")
    messages = state["messages"]
    
    if len(messages) == 1:
        messages_with_prompt = [
            HumanMessage(content=system_prompt), 
            messages[0] 
        ]
    else:
        messages_with_prompt = messages

    response = model_with_tools.invoke(messages_with_prompt)
    return {"messages": [response]}

def call_tools(state: AgentState):
    """Executa as ferramentas que o agente decidiu usar E faz o roteamento lógico."""
    print("--- Nó: call_tools (Ação) ---")
    last_message = state["messages"][-1]
    
    if not last_message.tool_calls:
        print("Agente não chamou ferramentas. Fim do passo.")
        return {}

    tool_messages = []
    excel_path = state.get("excel_file_path") 
    app_mode = state["app_mode"] 

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        print(f"Agente chamou ferramenta: {tool_name}")
        args = tool_call["args"]
        
        try:
            resultado_msg_para_agente = ""
            
            # Lógica de Roteamento (Sem mudanças)
            if tool_name == "salvar_dados_nota":
                print(f"Roteamento de salvamento. Modo atual: {app_mode}")
                dados_pydantic = DadosNotaFiscal(**args['dados_nota'])
                
                if app_mode == 'single':
                    resultado = salvar_dados_em_excel(dados_pydantic) 
                else: # 'accumulated'
                    resultado = acumular_dados_em_excel(dados_pydantic)
                
                if not str(resultado).startswith("Erro"):
                    excel_path = str(resultado) 
                    if app_mode == 'single':
                         resultado_msg_para_agente = f"Arquivo salvo com sucesso em: {excel_path}"
                    else:
                         resultado_msg_para_agente = f"Dados ACUMULADOS com sucesso em: {excel_path}"
                else:
                    resultado_msg_para_agente = str(resultado)
            
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

    return {"messages": tool_messages, "excel_file_path": excel_path}


# --- 7. Definir a "Lógica" (Sem mudanças) ---
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return END

# --- 8. Montar e Compilar o Gráfico (Sem mudanças) ---
print("Compilando o workflow do agente (v3.0 - Campos Expandidos)...")
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("action", call_tools)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"action": "action", END: END})
workflow.add_edge("action", "agent")
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
print("Workflow compilado com sucesso!")