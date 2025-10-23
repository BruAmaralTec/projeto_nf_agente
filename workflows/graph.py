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
    salvar_dados_nota,  # <-- A ÚNICA ferramenta de salvar que o LLM vê
    
    # Funções de lógica interna que o LLM NÃO VÊ
    salvar_dados_em_excel,
    acumular_dados_em_excel,
    
    DadosNotaFiscal 
)

# Carregar as variáveis de ambiente (nosso .env)
from dotenv import load_dotenv
load_dotenv()

# --- 2. Definir as Ferramentas para o Agente ---
# A lista agora é menor. O LLM não sabe que existem dois modos de salvar.
tools = [
    extrair_dados_xml, 
    extrair_texto_imagem, 
    extrair_texto_pdf, 
    extrair_texto_html,
    salvar_dados_nota # <-- SÓ A FERRAMENTA GENÉRICA
]

# --- 3. Definir o Modelo (LLM) ---
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
model_with_tools = model.bind_tools(tools)

# --- 4. Definir as Instruções (System Prompt) ---
# O prompt agora é MAIS SIMPLES
system_prompt = """
Você é um assistente especialista em processamento de notas fiscais brasileiras.
Sua missão é seguir um processo de duas etapas:

Etapa 1: Extração de Dados Brutos.
- O usuário fornecerá o caminho para um arquivo (XML, PDF, HTML, PNG, JPG).
- Você DEVE escolher a ferramenta de extração de dados CORRETA com base no tipo de arquivo.
  - Para .xml, use 'extrair_dados_xml'.
  - Para .pdf, use 'extrair_texto_pdf'.
  - Para .html, use 'extrair_texto_html'.
  - Para .png, .jpg, ou .jpeg, use 'extrair_texto_imagem'.
- Você receberá o texto bruto extraído pela ferramenta.

Etapa 2: Formatação e Salvamento.
- Após receber o texto bruto, analise-o.
- Extraia os campos principais: cnpj_emitente, nome_emitente, cnpj_cpf_destinatario, nome_destinatario, chave_acesso, e valor_total.
- Use o seu conhecimento para limpar os dados.
- Quando tiver todos os dados estruturados, você DEVE chamar a ferramenta 'salvar_dados_nota'.
- O sistema interno cuidará de como salvar. Você não precisa se preocupar com isso.
"""

# --- 5. Definir o "Estado" do Agente (A Memória) ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    file_path: str
    excel_file_path: Optional[str] = None
    app_mode: str # Guarda 'single' ou 'accumulated'

# --- 6. Definir os "Nós" do Gráfico (As Etapas) ---

# Nó call_model (NÃO PRECISA MAIS INJETAR O MODO)
def call_model(state: AgentState):
    """Chama o LLM para decidir o próximo passo."""
    print("--- Nó: call_model (Agente) ---")
    messages = state["messages"]
    
    # Não precisamos mais injetar o modo! O prompt é sempre o mesmo.
    if len(messages) == 1:
        messages_with_prompt = [
            HumanMessage(content=system_prompt), 
            messages[0] 
        ]
    else:
        messages_with_prompt = messages

    response = model_with_tools.invoke(messages_with_prompt)
    return {"messages": [response]}

# NÓ ATUALIZADO: call_tools (Onde a Mágica Acontece)
def call_tools(state: AgentState):
    """Executa as ferramentas que o agente decidiu usar E faz o roteamento lógico."""
    print("--- Nó: call_tools (Ação) ---")
    last_message = state["messages"][-1]
    
    if not last_message.tool_calls:
        print("Agente não chamou ferramentas. Fim do passo.")
        return {}

    tool_messages = []
    excel_path = state.get("excel_file_path") 
    app_mode = state["app_mode"] # Pega o modo do estado

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        print(f"Agente chamou ferramenta: {tool_name}")
        args = tool_call["args"]
        
        try:
            resultado_msg_para_agente = ""
            
            # --- MUDANÇA CRUCIAL: LÓGICA DE ROTEAMENTO ---
            if tool_name == "salvar_dados_nota":
                # O Agente chamou a ferramenta genérica.
                # Agora NÓS (Python) vamos decidir qual função real chamar.
                
                print(f"Roteamento de salvamento. Modo atual: {app_mode}")
                dados_pydantic = DadosNotaFiscal(**args['dados_nota'])
                
                if app_mode == 'single':
                    # Chama a função de salvamento único
                    resultado = salvar_dados_em_excel(dados_pydantic) 
                else: # 'accumulated'
                    # Chama a função de salvamento acumulado
                    resultado = acumular_dados_em_excel(dados_pydantic)
                
                # Prepara a resposta
                if not str(resultado).startswith("Erro"):
                    excel_path = str(resultado) # Atualiza o estado
                    if app_mode == 'single':
                         resultado_msg_para_agente = f"Arquivo salvo com sucesso em: {excel_path}"
                    else:
                         resultado_msg_para_agente = f"Dados ACUMULADOS com sucesso em: {excel_path}"
                else:
                    resultado_msg_para_agente = str(resultado) # Passa a msg de erro
            
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
print("Compilando o workflow do agente (v2.9 - Roteador)...")
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("action", call_tools)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"action": "action", END: END})
workflow.add_edge("action", "agent")
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
print("Workflow compilado com sucesso!")