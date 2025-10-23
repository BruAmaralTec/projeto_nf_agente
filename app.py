import streamlit as st
import os
import uuid
from workflows.graph import app  # Nosso cérebro de agente!
from langchain_core.messages import HumanMessage

# --- CSS (Sem mudanças) ---
NOVA_COR_PRIMARIA = "#C0FF72"
NOVA_COR_SECUNDARIA = "#A9E64B"
NOVA_COR_HOVER = "#98CC42"
TEXTO_COR = "#000000"
st.markdown(
    f"""
    <style>
    [data-testid="stSidebar"] {{ background-color: {NOVA_COR_PRIMARIA}; color: {TEXTO_COR}; }}
    [data-testid="stSidebar"] .st-emotion-cache-1pxjwj4 {{ color: {TEXTO_COR}; }}
    .st-emotion-cache-10qj7k0, [data-testid="stButton"] button {{ background-color: {NOVA_COR_SECUNDARIA} !important; color: {TEXTO_COR} !important; border: 1px solid {NOVA_COR_HOVER}; }}
    .st-emotion-cache-10qj7k0:hover, [data-testid="stButton"] button:hover {{ background-color: {NOVA_COR_HOVER} !important; border: 1px solid {NOVA_COR_HOVER}; }}
    .st-emotion-cache-7ym5gk {{ transition: transform 0.1s ease-in-out; }}
    .st-emotion-cache-7ym5gk:hover {{ transform: scale(1.02); }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- Configuração da Página (Sem mudanças) ---
st.set_page_config(
    page_title="Meta Singularity - Agente NF",
    page_icon="assets/logo_meta_singularity.png",
    layout="wide",
    initial_sidebar_state="auto",
)

# --- Diretórios (Sem mudanças) ---
UPLOAD_DIR = "dados_upload"
OUTPUT_DIR = "dados_saida"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Gerenciamento de Estado Principal ---
if "app_mode" not in st.session_state:
    st.session_state.app_mode = None
    
# --- MUDANÇA 1: Inicializa a nossa "trava" de estado ---
if "file_just_processed" not in st.session_state:
    st.session_state.file_just_processed = False

# --- TELA INICIAL (Sem mudanças) ---
if st.session_state.app_mode is None:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    col_logo, col_title = st.columns([1, 3])
    with col_logo: st.image("assets/logo_meta_singularity.png", width=250)
    with col_title:
        st.title("Bem-vindo ao Agente da Meta Singularity")
        st.header("Sistema Inteligente de Extração de NF")
    st.markdown("---")
    st.subheader("Por favor, selecione o modo de operação:")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 1. Modo: Arquivo Único")
            st.markdown("Processe um único arquivo...")
            if st.button("Iniciar Processamento Único", use_container_width=True, type="primary"):
                st.session_state.app_mode = "single"
                st.rerun() 
    with col2:
        with st.container(border=True):
            st.markdown("### 2. Modo: Compilado")
            st.markdown("Processe múltiplos arquivos...")
            if st.button("Iniciar Processamento Compilado", use_container_width=True, type="primary"):
                st.session_state.app_mode = "accumulated"
                st.rerun() 

# --- TELA PRINCIPAL DO APLICATIVO (Chat) ---
else:
    # --- Barra Lateral (Sem mudanças) ---
    with st.sidebar:
        st.image("assets/logo_meta_singularity.png", width=200)
        st.title("Meta Singularity")
        st.header("🤖 Agente Extrator de NF")
        st.markdown("---")
        modo_atual = "Arquivo Único" if st.session_state.app_mode == "single" else "Compilado"
        st.markdown(f"**Modo Atual:** `{modo_atual}`")
        if st.button("Mudar Modo / Voltar ao Início"):
            st.session_state.app_mode = None 
            st.session_state.messages = [] 
            st.session_state.file_just_processed = False # Reseta a trava
            st.rerun() 
        st.markdown("---")
        st.caption("Repositório do Projeto: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agente)") 

    st.header(f"Chat de Processamento - Modo: {modo_atual}")
    
    # --- Memória de Chat (Sem mudanças) ---
    if "session_id" not in st.session_state: st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state: st.session_state.messages = []
    if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": st.session_state.session_id}}

    # --- Renderização do Histórico de Chat (Sem mudanças) ---
    for i, message in enumerate(st.session_state.messages):
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
                            key=f"history_btn_{i}"
                        )

    # --- Widget de Upload de Arquivo ---
    uploaded_file_widget = st.file_uploader(
        "Faça o upload da sua Nota Fiscal aqui:", 
        type=["pdf", "xml", "html", "png", "jpg", "jpeg"],
        label_visibility="collapsed"
        # Removemos a 'key' para simplificar, a nova lógica não precisa dela
    )

    # --- MUDANÇA 2: Lógica de Processamento com a "Trava" ---
    # Só processa se o widget NÃO for nulo E a trava "just_processed" for False
    if uploaded_file_widget is not None and not st.session_state.file_just_processed:
        
        # --- MUDANÇA 3: Ativa a trava IMEDIATAMENTE ---
        st.session_state.file_just_processed = True

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
                    "excel_file_path": None,
                    "app_mode": st.session_state.app_mode
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
                            key=f"new_btn_{len(st.session_state.messages)}"
                        )
        
        st.rerun() # Recarrega a página para o estado "estável"

    # --- MUDANÇA 4: Lógica para "Destravar" ---
    # Se o uploader está vazio (usuário limpou) E a trava está ativa, desativa a trava.
    elif uploaded_file_widget is None and st.session_state.file_just_processed:
        st.session_state.file_just_processed = False