import uuid
from workflows.graph import app # Importamos o "app" compilado do nosso grafo
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import os

# --- Configuração do Teste ---
arquivo_para_teste = "dados_teste/nota_exemplo.pdf"

if not os.path.exists(arquivo_para_teste):
    print(f"ERRO: Arquivo de teste não encontrado em {arquivo_para_teste}")
else:
    print(f"Iniciando teste do agente com o arquivo: {arquivo_para_teste}")
    
    # Cada conversa precisa de um ID único para a memória funcionar
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    mensagem_usuario = f"Por favor, processe esta nota fiscal. O caminho do arquivo é: {arquivo_para_teste}"
    
    estado_inicial = {
        "messages": [HumanMessage(content=mensagem_usuario)],
        "file_path": arquivo_para_teste,
        "excel_file_path": None
    }
    
    print("\n--- INICIANDO CONVERSA COM O AGENTE ---")
    
    try:
        # Usamos .stream() para ver o agente "pensar" passo a passo
        for event in app.stream(estado_inicial, config):
            for key, value in event.items():
                print(f"\nExecutando nó: {key}")
                
                if "messages" in value:
                    print("Mensagens no estado:")
                    for msg in value["messages"]:
                        print(f"  - [{msg.type.upper()}]:")
                        
                        # --- AQUI ESTÁ A MUDANÇA ---
                        # Imprime o conteúdo, que todas têm
                        print(f"     - Conteúdo: {msg.content}")
                        
                        # Se for uma AIMessage, verifica se tem tool_calls
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            print("     - Chamadas de Ferramenta:")
                            for tool in msg.tool_calls:
                                print(f"       - Nome: {tool['name']}")
                                print(f"       - Args: {tool['args']}")
                        
                        # Se for uma ToolMessage, imprime o ID
                        if isinstance(msg, ToolMessage):
                            print(f"     - ID da Ferramenta: {msg.tool_call_id}")

    except Exception as e:
        print(f"\n--- ERRO DURANTE A EXECUÇÃO DO GRAFO ---")
        print(e)

    print("\n--- FIM DA CONVERSA ---")
    
    try:
        # No final, vamos checar o estado final da memória
        estado_final = app.get_state(config)
        print("\n--- ESTADO FINAL DA MEMÓRIA ---")
        
        if estado_final.values and 'messages' in estado_final.values:
            mensagem_final_agente = estado_final.values['messages'][-1]
            print(f"Última mensagem do Agente: {mensagem_final_agente.content}")
            print(f"Caminho do Excel salvo: {estado_final.values.get('excel_file_path', 'Não salvo')}")
        else:
            print("Não foi possível recuperar o estado final.")
            
    except Exception as e:
        print(f"\n--- ERRO AO OBTER ESTADO FINAL ---")
        print(e)