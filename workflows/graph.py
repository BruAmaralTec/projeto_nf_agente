import os
import pandas as pd
from typing import TypedDict, Annotated, List, Union, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import operator

# --- 1. Importar NOSSAS 5 FERRAMENTAS ---
from tools.extracao import (
    extrair_dados_xml, 
    extrair_texto_imagem, 
    extrair_texto_pdf, 
    extrair_texto_html,
    salvar_dados_em_excel,
    DadosNotaFiscal # Importamos o "molde" também
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
    salvar_dados_em_excel
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
  - Para .xml, use 'extrair_dados_xml'.
  - Para .pdf, use 'extrair_texto_pdf'.
  - Para .html, use 'extrair_texto_html'.
  - Para .png, .jpg, ou .jpeg, use 'extrair_texto_imagem'.
- Você receberá o texto bruto extraído pela ferramenta.

Etapa 2: Formatação e Salvamento.
- Após receber o texto bruto, analise-o.
- Extraia os campos principais: cnpj_emitente, nome_emitente, cnpj_cpf_destinatario, nome_destinatario, chave_acesso, e valor_total.
- Use o seu conhecimento para limpar os dados (ex: remover 'R$' do valor, manter apenas números em CNPJs).
- Quando tiver todos os dados estruturados, você DEVE chamar a ferramenta 'salvar_dados_em_excel' para salvar o resultado.
- NUNCA chame 'salvar_dados_em_excel' antes de ter os dados.
- Ao final, informe ao usuário que o arquivo foi salvo e o caminho dele.
"""

# --- 5. Definir o "Estado" do Agente (A Memória) ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    file_path: str
    excel_file_path: Optional[str] = None

# --- 6. Definir os "Nós" do Gráfico (As Etapas) ---

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

# --- NÓ DE FERRAMENTAS (COM A CORREÇÃO) ---
def call_tools(state: AgentState):
    """Executa as ferramentas que o agente decidiu usar E atualiza o estado."""
    print("--- Nó: call_tools (Ação) ---")
    last_message = state["messages"][-1]
    
    if not last_message.tool_calls:
        print("Agente não chamou ferramentas. Fim do passo.")
        return {} # Retorna dicionário vazio

    tool_messages = []
    
    # Pega o valor atual do excel_file_path, caso ele não seja modificado
    excel_path = state.get("excel_file_path") 

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        print(f"Executando ferramenta: {tool_name}")
        args = tool_call["args"]
        
        # Injeta o file_path do estado nos argumentos das ferramentas de extração
        if tool_name == "extrair_dados_xml": args = {"caminho_do_arquivo_xml": state["file_path"]}
        if tool_name == "extrair_texto_imagem": args = {"caminho_do_arquivo_imagem": state["file_path"]}
        if tool_name == "extrair_texto_pdf": args = {"caminho_do_arquivo_pdf": state["file_path"]}
        if tool_name == "extrair_texto_html": args = {"caminho_do_arquivo_html": state["file_path"]}
        
        try:
            # Chama a ferramenta
            if tool_name == "salvar_dados_em_excel":
                dados_pydantic = DadosNotaFiscal(**args['dados_nota'])
                resultado = salvar_dados_em_excel.func(dados_pydantic)
                
                # --- LÓGICA DE ATUALIZAÇÃO DO ESTADO ---
                if not str(resultado).startswith("Erro"):
                    excel_path = str(resultado) # Atualiza a variável
                    resultado_msg_para_agente = f"Arquivo salvo com sucesso em: {excel_path}"
                else:
                    resultado_msg_para_agente = str(resultado) # Passa a msg de erro
            
            else:
                # Chama ferramentas de extração
                ferramenta = globals()[tool_name]
                resultado = ferramenta.func(**args)
                resultado_msg_para_agente = str(resultado)
                
            tool_messages.append(ToolMessage(content=resultado_msg_para_agente, tool_call_id=tool_call["id"]))

        except Exception as e:
            print(f"Erro ao executar ferramenta {tool_name}: {e}")
            tool_messages.append(ToolMessage(content=f"Erro: {e}", tool_call_id=tool_call["id"]))

    # --- O RETORNO CORRETO DO LANGGRAPH ---
    # Retorna as mensagens E o novo estado do excel_file_path
    return {"messages": tool_messages, "excel_file_path": excel_path}


# --- 7. Definir a "Lógica" (As Arestas/Edges) ---
def should_continue(state: AgentState):
    """Decide se continua chamando ferramentas ou se termina."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return END

# --- 8. Montar e Compilar o Gráfico ---
print("Compilando o workflow do agente...")

workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("action", call_tools)

workflow.add_edge(START, "agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "action": "action",
        END: END
    }
)
workflow.add_edge("action", "agent")

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

print("Workflow compilado com sucesso!")