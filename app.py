import streamlit as st
import os
import uuid
from workflows.graph import app  # Nosso cérebro de agente!
from langchain_core.messages import HumanMessage

# --- Configuração da Página ---
st.set_page_config(
    page_title="Meta Singularity - Agente NF",
    page_icon="🤖",
    layout="wide",
    
    # --- MUDANÇA AQUI ---
    initial_sidebar_state="auto", # Era "expanded"
    # --- FIM DA MUDANÇA ---
)

# --- Diretórios ---
UPLOAD_DIR = "dados_upload"
OUTPUT_DIR = "dados_saida"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.image("https://storage.googleapis.com/gen-ai-samples/images/google-logo-wordmark.svg", width=200)
    st.title("Meta Singularity")
    st.header("🤖 Agente Extrator de NF")
    st.markdown("---")
    st.markdown("Este projeto usa Agentes Autônomos (LangGraph) para ler, analisar e extrair dados de Notas Fiscais em múltiplos formatos.")
    st.markdown("### 1. Faça o Upload")
    st.markdown("Use a área de chat para enviar um arquivo (.xml, .pdf, .html, .png, .jpg).")
    st.markdown("### 2. Aguarde o Processamento")
    st.markdown("O Agente irá identificar o arquivo, extrair os dados e formatá-los.")
    st.markdown("### 3. Baixe o Excel")
    st.markdown("Um link para download do arquivo .xlsx aparecerá no chat.")
    st.markdown("---")
    st.caption("Repositório do Projeto: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agente)") 

# --- Título Principal (no topo da área de chat) ---
st.header("Chat de Processamento de Notas Fiscais")

# --- Memória de Chat do Streamlit ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "thread_config" not in st.session_state:
    st.session_state.thread_config = {"configurable": {"thread_id": st.session_state.session_id}}

# --- Renderização do Histórico de Chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
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
uploaded_file_widget = st.file_uploader(
    "Faça o upload da sua Nota Fiscal aqui:", 
    type=["pdf", "xml", "html", "png", "jpg", "jpeg"],
    label_visibility="collapsed"
)


if uploaded_file_widget is not None:
    
    uploaded_file = uploaded_file_widget 
    temp_file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    prompt_tecnico = f"Por favor, processe esta nota fiscal. O caminho do arquivo é: {temp_file_path}"
    prompt_bonito = f"Processando arquivo: `{uploaded_file.name}`"
    
    st.session_state.messages.append({"role": "user", "content": prompt_bonito})
    with st.chat_message("user"):
        st.markdown(prompt_bonito)

    with st.chat_message("assistant"):
        with st.spinner("O Agente está pensando... 🧠"):
            
            estado_inicial = {
                "messages": [HumanMessage(content=prompt_tecnico)],
                "file_path": temp_file_path,
                "excel_file_path": None
            }
            
            final_state = app.invoke(estado_inicial, config=st.session_state.thread_config)

            response_message = final_state["messages"][-1]
            response_content = response_message.content
            excel_path_final = final_state.get("excel_file_path")
            
            st.markdown(response_content)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_content,
                "excel_path": excel_path_final
            })
            
            if excel_path_final and os.path.exists(excel_path_final):
                with open(excel_path_final, "rb") as f:
                    st.download_button(
                        label=f"Download {os.path.basename(excel_path_final)}",
                        data=f,
                        file_name=os.path.basename(excel_path_final),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download_btn_{st.session_state.session_id}" 
                    )
            
            st.rerun()