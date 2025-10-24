import streamlit as st
import os
import uuid
from workflows.graph import app  # Nosso cérebro de agente!
from langchain_core.messages import HumanMessage
import time # Para adicionar um pequeno delay visual

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
    st.session_state.app_mode = None  # None, 'single', 'accumulated'

# --- MUDANÇA 1: Novo estado para o modo compilado ---
if "compiled_upload_method" not in st.session_state:
    # None: Mostra a escolha; 'single': Upload individual; 'multiple': Upload múltiplo
    st.session_state.compiled_upload_method = None 

if "file_just_processed" not in st.session_state:
    st.session_state.file_just_processed = False
    
# --- Funções Auxiliares ---
def reset_to_main_menu():
    """Reseta todos os estados para voltar à tela inicial."""
    st.session_state.app_mode = None
    st.session_state.compiled_upload_method = None
    st.session_state.messages = []
    st.session_state.file_just_processed = False
    # Não resetamos session_id ou thread_config para manter a memória do agente entre modos

def render_chat_history():
    """Desenha o histórico do chat e os botões de download."""
    if "messages" not in st.session_state: st.session_state.messages = []
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "excel_path" in message:
                excel_path = message["excel_path"]
                if excel_path and os.path.exists(excel_path): # Verifica se excel_path não é None
                    with open(excel_path, "rb") as f:
                        st.download_button(
                            label=f"Download {os.path.basename(excel_path)}",
                            data=f,
                            file_name=os.path.basename(excel_path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"history_btn_{st.session_state.app_mode}_{st.session_state.compiled_upload_method}_{i}" # Chave mais única
                        )

def render_sidebar():
    """Desenha a barra lateral padrão."""
    with st.sidebar:
        st.image("assets/logo_meta_singularity.png", width=200)
        st.title("Meta Singularity")
        st.header("🤖 Agente Extrator de NF")
        st.markdown("---")
        
        modo_atual = "Arquivo Único" if st.session_state.app_mode == "single" else "Compilado"
        st.markdown(f"**Modo Atual:** `{modo_atual}`")
        if st.session_state.compiled_upload_method:
             sub_modo = "Individual" if st.session_state.compiled_upload_method == 'single' else "Múltiplos Arquivos"
             st.markdown(f"**Método Upload:** `{sub_modo}`")

        if st.button("Mudar Modo / Voltar ao Início"):
            reset_to_main_menu()
            st.rerun() 
            
        st.markdown("---")
        st.caption("Repositório do Projeto: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agent)") 

# --- ROTEAMENTO PRINCIPAL ---

# 1. TELA INICIAL
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
            st.markdown("Gere um Excel separado para cada nota fiscal.")
            if st.button("Iniciar Processamento Único", use_container_width=True, type="primary", key="btn_single_mode"):
                st.session_state.app_mode = "single"
                st.session_state.compiled_upload_method = None # Garante reset
                st.rerun() 
    with col2:
        with st.container(border=True):
            st.markdown("### 2. Modo: Compilado")
            st.markdown("Acumule dados de várias notas em um único Excel.")
            if st.button("Iniciar Processamento Compilado", use_container_width=True, type="primary", key="btn_compiled_mode"):
                st.session_state.app_mode = "accumulated"
                st.session_state.compiled_upload_method = None # Vai para a tela de escolha
                st.rerun() 

# 2. MODO ARQUIVO ÚNICO (Interface de Chat Normal)
elif st.session_state.app_mode == "single":
    render_sidebar()
    st.header(f"Chat de Processamento - Modo: Arquivo Único")
    
    # Renderiza histórico antes dos controles
    render_chat_history()

    # Lógica de Upload/Reset para Modo Único
    if st.session_state.file_just_processed:
        st.info("Processamento concluído. Você pode baixar o arquivo no chat acima.")
        if st.button("Subir Novo Arquivo", use_container_width=True, type="primary", key="reset_single"):
            st.session_state.file_just_processed = False
            st.rerun()
    else:
        uploaded_file_widget = st.file_uploader(
            "Faça o upload da sua Nota Fiscal aqui:", 
            type=["pdf", "xml", "html", "png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key="uploader_single" # Chave específica
        )

        if uploaded_file_widget is not None:
            st.session_state.file_just_processed = True
            # --- Inicia o processamento ---
            uploaded_file = uploaded_file_widget 
            temp_file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
            with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
            prompt_tecnico = f"Processar: {temp_file_path}"
            prompt_bonito = f"Processando arquivo: `{uploaded_file.name}`"
            if "messages" not in st.session_state: st.session_state.messages = []
            st.session_state.messages.append({"role": "user", "content": prompt_bonito})
            with st.chat_message("user"): st.markdown(prompt_bonito)
            with st.chat_message("assistant"):
                with st.spinner("O Agente está pensando... 🧠"):
                    estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "single"}
                    if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                    final_state = app.invoke(estado_inicial, config=st.session_state.thread_config)
                    response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                    st.markdown(response_content)
                    st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
                    # Botão de download imediato (já está no render_chat_history na próxima recarga)
            st.rerun()

# 3. MODO COMPILADO
elif st.session_state.app_mode == "accumulated":
    render_sidebar() # Mostra a sidebar em todas as sub-telas do compilado
    
    # 3.1 TELA DE ESCOLHA DO MÉTODO DE UPLOAD
    if st.session_state.compiled_upload_method is None:
        st.header("Modo Compilado - Escolha o Método de Upload")
        st.markdown("Como você prefere enviar os arquivos para serem compilados?")
        
        col1, col2 = st.columns(2)
        with col1:
             with st.container(border=True):
                 st.markdown("#### A. Múltiplos Arquivos de Uma Vez")
                 st.markdown("Selecione vários arquivos (.pdf, .xml, etc.) da mesma pasta. O sistema processará todos em sequência.")
                 if st.button("Selecionar Múltiplos Arquivos", use_container_width=True, key="btn_multi_select"):
                     st.session_state.compiled_upload_method = 'multiple'
                     st.session_state.file_just_processed = False # Garante reset da trava
                     st.rerun()
        with col2:
            with st.container(border=True):
                st.markdown("#### B. Um Arquivo por Vez")
                st.markdown("Faça o upload de um arquivo, veja o resultado, e suba o próximo, acumulando os dados no mesmo arquivo mestre.")
                if st.button("Subir Arquivo Individualmente", use_container_width=True, key="btn_single_select"):
                    st.session_state.compiled_upload_method = 'single'
                    st.session_state.file_just_processed = False # Garante reset da trava
                    st.rerun()

    # 3.2 MÉTODO: UPLOAD INDIVIDUAL (Interface de Chat)
    elif st.session_state.compiled_upload_method == 'single':
        st.header(f"Chat de Processamento - Modo: Compilado (Individual)")
        render_chat_history()

        if st.session_state.file_just_processed:
            st.info("Processamento concluído. Dados acumulados no arquivo mestre. Você pode baixar a versão atualizada no chat acima.")
            if st.button("Subir Próximo Arquivo", use_container_width=True, type="primary", key="reset_compiled_single"):
                st.session_state.file_just_processed = False
                st.rerun()
        else:
            uploaded_file_widget = st.file_uploader(
                "Faça o upload do próximo arquivo para o compilado:", 
                type=["pdf", "xml", "html", "png", "jpg", "jpeg"],
                label_visibility="collapsed",
                key="uploader_compiled_single"
            )
            if uploaded_file_widget is not None:
                st.session_state.file_just_processed = True
                # --- Inicia o processamento ---
                uploaded_file = uploaded_file_widget 
                temp_file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                prompt_tecnico = f"Processar: {temp_file_path}"
                prompt_bonito = f"Acumulando dados do arquivo: `{uploaded_file.name}`"
                if "messages" not in st.session_state: st.session_state.messages = []
                st.session_state.messages.append({"role": "user", "content": prompt_bonito})
                with st.chat_message("user"): st.markdown(prompt_bonito)
                with st.chat_message("assistant"):
                    with st.spinner("O Agente está acumulando os dados... 🧠"):
                        estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "accumulated"} # MODO CORRETO
                        if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                        final_state = app.invoke(estado_inicial, config=st.session_state.thread_config)
                        response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                        st.markdown(response_content)
                        st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
                st.rerun()

    # 3.3 MÉTODO: UPLOAD MÚLTIPLO
    elif st.session_state.compiled_upload_method == 'multiple':
        st.header(f"Chat de Processamento - Modo: Compilado (Múltiplos Arquivos)")
        
        # Renderiza histórico ANTES do uploader
        render_chat_history()
        
        # Lógica de Upload/Reset para Múltiplos
        if st.session_state.file_just_processed:
            st.success("Todos os arquivos selecionados foram processados! Dados acumulados no arquivo mestre. Você pode baixar a versão final no chat acima.")
            if st.button("Subir Novo Lote de Arquivos", use_container_width=True, type="primary", key="reset_compiled_multiple"):
                st.session_state.file_just_processed = False
                st.rerun()
        else:
            uploaded_files_widget = st.file_uploader(
                "Selecione múltiplos arquivos (.pdf, .xml, .html, .png, .jpg) para compilar:", 
                type=["pdf", "xml", "html", "png", "jpg", "jpeg"],
                accept_multiple_files=True, # <-- A MÁGICA ACONTECE AQUI
                label_visibility="collapsed",
                key="uploader_compiled_multiple"
            )

            if uploaded_files_widget: # Verifica se a lista não está vazia
                st.session_state.file_just_processed = True
                
                total_files = len(uploaded_files_widget)
                st.info(f"Processando {total_files} arquivos...")
                
                progress_bar = st.progress(0, text="Iniciando processamento...")
                
                # Guarda o caminho do último arquivo processado para o botão de download final
                last_excel_path = None 
                
                if "messages" not in st.session_state: st.session_state.messages = []
                if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

                for i, uploaded_file in enumerate(uploaded_files_widget):
                    file_name = uploaded_file.name
                    progress_text = f"Processando arquivo {i+1}/{total_files}: {file_name}"
                    progress_bar.progress((i + 1) / total_files, text=progress_text)
                    
                    # Salva temporariamente
                    temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file_name}") # Nome único para evitar conflitos
                    with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    
                    # Mostra no chat
                    prompt_bonito = f"Acumulando dados do arquivo ({i+1}/{total_files}): `{file_name}`"
                    st.session_state.messages.append({"role": "user", "content": prompt_bonito})
                    with st.chat_message("user"): st.markdown(prompt_bonito)

                    # Chama o agente
                    with st.chat_message("assistant"):
                        with st.spinner(f"Agente analisando {file_name}..."):
                             prompt_tecnico = f"Processar: {temp_file_path}"
                             estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "accumulated"}
                             final_state = app.invoke(estado_inicial, config=st.session_state.thread_config)
                             
                             response_message = final_state["messages"][-1]
                             response_content = response_message.content
                             excel_path_final = final_state.get("excel_file_path")
                             last_excel_path = excel_path_final # Guarda o caminho do último
                             
                             st.markdown(response_content)
                             st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final}) # Adiciona ao histórico para o botão aparecer
                             
                    # Limpa o arquivo temporário após o uso (opcional, mas boa prática)
                    # try: os.remove(temp_file_path)
                    # except OSError as e: print(f"Erro ao remover arquivo temp: {e}")
                    
                    time.sleep(0.5) # Pequeno delay visual

                progress_bar.empty() # Limpa a barra de progresso
                
                # Adiciona uma mensagem final ao chat (sem botão de download aqui, ele está no histórico)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"Processamento de {total_files} arquivos concluído. O arquivo mestre foi atualizado.",
                    "excel_path": last_excel_path # Associa o último caminho ao botão final
                })
                
                st.rerun() # Recarrega para mostrar o botão "Subir Novo Lote"