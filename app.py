import streamlit as st
import os
import uuid
from workflows.graph import app  # Nosso cérebro de agente!
from langchain_core.messages import HumanMessage

# --- Configuração da Página ---
st.set_page_config(
    page_title="Agente Extrator de NF",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 Agente Autônomo Extrator de Notas Fiscais")
st.caption("Faça o upload de uma NF (.xml, .pdf, .html, .png, .jpg) e o agente irá processá-la.")

# --- Diretórios ---
# Precisamos de um local para salvar os arquivos de upload temporariamente
UPLOAD_DIR = "dados_upload"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# O diretório de saída que nosso agente já usa
OUTPUT_DIR = "dados_saida"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Memória de Chat do Streamlit ---
# Vamos usar o 'st.session_state' para guardar o histórico da conversa e o ID da thread
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "thread_config" not in st.session_state:
    st.session_state.thread_config = {"configurable": {"thread_id": st.session_state.session_id}}
    
# --- Renderização do Histórico de Chat ---
# Mostra as mensagens antigas
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Se for uma mensagem do assistente E tiver um arquivo Excel, mostra o botão de download
        if message["role"] == "assistant" and "excel_path" in message:
            excel_path = message["excel_path"]
            if os.path.exists(excel_path):
                with open(excel_path, "rb") as f:
                    st.download_button(
                        label=f"Download {os.path.basename(excel_path)}",
                        data=f,
                        file_name=os.path.basename(excel_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

# --- Widget de Upload de Arquivo ---
uploaded_file = st.file_uploader(
    "Selecione o arquivo da Nota Fiscal:", 
    type=["pdf", "xml", "html", "png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    # 1. Salvar o arquivo temporariamente
    # O agente precisa de um CAMINHO no disco, não de um objeto em memória
    temp_file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")

    # 2. Criar o prompt para o agente
    prompt = f"Por favor, processe esta nota fiscal. O caminho do arquivo é: {temp_file_path}"
    
    # 3. Adicionar a mensagem humana ao chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 4. Chamar o agente (o cérebro)
    with st.chat_message("assistant"):
        with st.spinner("O Agente está pensando... 🧠"):
            
            # Prepara o estado inicial para o grafo
            estado_inicial = {
                "messages": [HumanMessage(content=prompt)],
                "file_path": temp_file_path, # O caminho do arquivo que salvamos
                "excel_file_path": None
            }
            
            # Invoca o agente!
            # Usamos .invoke() aqui em vez de .stream() para obter a resposta final
            final_state = app.invoke(estado_inicial, config=st.session_state.thread_config)

            # 5. Obter a resposta final
            response_message = final_state["messages"][-1]
            response_content = response_message.content
            
            # 6. Obter o caminho do Excel salvo
            excel_path_final = final_state.get("excel_file_path")
            
            # 7. Mostrar a resposta e o botão de download
            st.markdown(response_content)
            
            # Guarda a resposta no histórico
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_content,
                "excel_path": excel_path_final # Guarda o caminho para renderizar o botão
            })
            
            # Se tiver um arquivo, mostra o botão de download IMEDIATAMENTE
            if excel_path_final and os.path.exists(excel_path_final):
                with open(excel_path_final, "rb") as f:
                    st.download_button(
                        label=f"Download {os.path.basename(excel_path_final)}",
                        data=f,
                        file_name=os.path.basename(excel_path_final),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )