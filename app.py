import streamlit as st
import os
import uuid
from workflows.graph import app  # Nosso cérebro de agente!
from langchain_core.messages import HumanMessage

# --- CSS Personalizado para a Barra Lateral e Estilo Geral ---
# A cor de fundo da sua imagem é #CFF798.
# Para manter a consistência, vamos usá-la como cor primária
# e um verde mais escuro (#A0E670) para elementos interativos.
st.markdown(
    f"""
    <style>
    /* Cor de fundo da barra lateral */
    [data-testid="stSidebar"] {{
        background-color: #CFF798; /* Cor de fundo da imagem da sua logo */
        color: #000000; /* Texto preto para contraste */
    }}
    /* Cor dos ícones e texto na barra lateral */
    [data-testid="stSidebar"] .st-emotion-cache-1pxjwj4 {{ /* Ajustar seletor conforme versão do streamlit */
        color: #000000;
    }}
    /* Cor primária para botões, sliders, etc. */
    .st-emotion-cache-10qj7k0 {{ /* Ajustar seletor conforme versão do streamlit para primary button */
        background-color: #A0E670; /* Verde um pouco mais escuro para botões */
        color: black !important;
    }}
    /* Cor de hover/ativo para botões */
    .st-emotion-cache-10qj7k0:hover {{
        background-color: #8FD550; /* Verde ainda mais escuro no hover */
        color: black !important;
    }}
    /* Cores do chat para melhor contraste com o fundo */
    [data-testid="stChatMessage"] p {{
        color: #333333; /* Cor do texto no chat */
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- Configuração da Página ---
st.set_page_config(
    page_title="Meta Singularity - Agente NF",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
)

# --- Diretórios ---
UPLOAD_DIR = "dados_upload"
OUTPUT_DIR = "dados_saida"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    # --- MUDANÇA DA LOGO AQUI ---
    st.image("assets/logo_meta_singularity.png", width=200) # Usando a sua imagem local
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