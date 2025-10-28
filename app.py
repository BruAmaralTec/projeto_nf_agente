import streamlit as st
import os
import uuid
from workflows.graph import app as langgraph_app # Renomeado para clareza
from langchain_core.messages import HumanMessage
import time

# --- Novas Importações para RAG ---
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Para a pipeline RAG
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate

# --- CSS Personalizado (Sem mudanças) ---
NOVA_COR_PRIMARIA_SIDEBAR = "#C0FF72" # Verde claro para sidebar
COR_BOTAO_PRINCIPAL = "#A9E64B"      # Verde médio para botões principais
COR_BOTAO_HOVER = "#98CC42"          # Verde escuro para hover principal
TEXTO_COR_SIDEBAR = "#000000"        # Texto preto na sidebar
COR_BOTAO_SIDEBAR = "#000000"         # Preto para botões da sidebar
TEXTO_BOTAO_SIDEBAR = "#FFFFFF"       # Texto branco nos botões da sidebar
COR_BOTAO_SIDEBAR_HOVER = "#333333"    # Cinza escuro para hover sidebar

st.markdown(
    f"""
    <style>
    /* --- Estilos Gerais --- */
    body {{ color: #333333; }}

    /* --- Barra Lateral --- */
    [data-testid="stSidebar"] {{ background-color: {NOVA_COR_PRIMARIA_SIDEBAR}; color: {TEXTO_COR_SIDEBAR}; }}
    [data-testid="stSidebar"] .st-emotion-cache-1pxjwj4 {{ color: {TEXTO_COR_SIDEBAR}; }}
    [data-testid="stSidebar"] .stCaption a {{ color: #1E88E5 !important; }}
    [data-testid="stSidebar"] .stCaption a:hover {{ color: #0D47A1 !important; }}

    /* --- Botões FORA da Sidebar --- */
    [data-testid="stButton"] button[kind="secondary"], .stButton>button:not([kind="primary"]):not(:hover) {{ /* Estilo opcional */ }}
    [data-testid="stButton"] button[kind="primary"], .st-emotion-cache-10qj7k0 {{
        background-color: {COR_BOTAO_PRINCIPAL} !important; color: {TEXTO_COR_SIDEBAR} !important;
        border: 1px solid {COR_BOTAO_HOVER}; transition: background-color 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stButton"] button[kind="primary"]:hover, .st-emotion-cache-10qj7k0:hover {{
        background-color: {COR_BOTAO_HOVER} !important; border-color: {COR_BOTAO_HOVER};
        color: {TEXTO_COR_SIDEBAR} !important;
    }}
    .st-emotion-cache-7ym5gk {{ transition: transform 0.1s ease-in-out; }}
    .st-emotion-cache-7ym5gk:hover {{ transform: scale(1.02); }}

    /* --- Botões DENTRO da Sidebar --- */
    [data-testid="stSidebar"] [data-testid="stButton"] button {{
        background-color: {COR_BOTAO_SIDEBAR} !important; color: {TEXTO_BOTAO_SIDEBAR} !important;
        border: 1px solid {COR_BOTAO_SIDEBAR_HOVER}; transition: background-color 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
        background-color: {COR_BOTAO_SIDEBAR_HOVER} !important; border-color: {COR_BOTAO_SIDEBAR_HOVER};
        color: {TEXTO_BOTAO_SIDEBAR} !important;
    }}

    /* --- Texto do Chat --- */
    [data-testid="stChatMessage"] p {{ color: #111111; }}
    </style>
    """,
    unsafe_allow_html=True
)


# --- Configuração da Página (Sem mudanças) ---
st.set_page_config( page_title="Meta Singularity - Agente NF", page_icon="assets/logo_meta_singularity.png", layout="wide", initial_sidebar_state="auto")

# --- Diretórios (Sem mudanças) ---
UPLOAD_DIR = "dados_upload"; OUTPUT_DIR = "dados_saida"
os.makedirs(UPLOAD_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Gerenciamento de Estado Principal (Sem mudanças) ---
if "app_mode" not in st.session_state: st.session_state.app_mode = None
if "compiled_upload_method" not in st.session_state: st.session_state.compiled_upload_method = None
if "file_just_processed" not in st.session_state: st.session_state.file_just_processed = False
if "rag_initialized" not in st.session_state: st.session_state.rag_initialized = False
if "rag_chain" not in st.session_state: st.session_state.rag_chain = None
if "rag_messages" not in st.session_state: st.session_state.rag_messages = []


# --- Funções Auxiliares (Sem mudanças) ---
def reset_to_main_menu():
    st.session_state.app_mode = None; st.session_state.compiled_upload_method = None
    st.session_state.messages = []; st.session_state.rag_messages = []
    st.session_state.file_just_processed = False

# --- Funções RAG (Sem mudanças na lógica interna) ---
@st.cache_resource
def initialize_rag_pipeline():
    try:
        doc_path = "docs/api_guide.md"
        if not os.path.exists(doc_path): # Cria guia inicial se não existir
             os.makedirs("docs", exist_ok=True)
             with open(doc_path, "w", encoding="utf-8") as f:
                 f.write("# Guia API Meta Singularity NF Extract\n\nEndpoint: `/processar_nf/` (POST)\n\n...") # Conteúdo básico
        loader = UnstructuredMarkdownLoader(doc_path)
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=50)
        splits = text_splitter.split_documents(docs)
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
        retriever = vectorstore.as_retriever()
        template = "Contexto: {context}\n\nPergunta: {question}\n\nUse APENAS o contexto para responder."
        prompt = ChatPromptTemplate.from_template(template)
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser())
        st.session_state.rag_initialized = True
        return rag_chain
    except Exception as e:
        st.error(f"Erro RAG Init: {e}"); st.session_state.rag_initialized = False; return None

# --- Funções de Renderização (Sem mudanças na lógica interna) ---
def render_chat_history(chat_type="agent"):
    messages_key = "messages" if chat_type == "agent" else "rag_messages"
    if messages_key not in st.session_state: st.session_state[messages_key] = []
    for i, message in enumerate(st.session_state[messages_key]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if chat_type == "agent" and message["role"] == "assistant" and "excel_path" in message:
                excel_path = message["excel_path"]
                if excel_path and isinstance(excel_path, str) and os.path.exists(excel_path):
                    try:
                        with open(excel_path, "rb") as f:
                            st.download_button(f"Download {os.path.basename(excel_path)}", f, os.path.basename(excel_path), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"hist_{chat_type}_{i}")
                    except Exception as e: st.error(f"Erro ao ler download: {e}")
                elif excel_path: st.caption(f"Arquivo '{os.path.basename(excel_path)}' não encontrado.")

def render_sidebar():
    with st.sidebar:
        st.image("assets/logo_meta_singularity.png", width=200); st.title("Meta Singularity"); st.header("🤖 Agente Extrator de NF"); st.markdown("---")
        if st.button("Guia Interativo da API", key="btn_goto_rag"): st.session_state.app_mode = "rag_chatbot"; st.session_state.compiled_upload_method = None; st.session_state.file_just_processed = False; st.rerun()
        st.markdown("---")
        if st.session_state.app_mode not in [None, "rag_chatbot"]:
            modo = "Único" if st.session_state.app_mode == "single" else "Compilado"; st.markdown(f"**Modo:** `{modo}`")
            if st.session_state.compiled_upload_method: sub = "Individual" if st.session_state.compiled_upload_method == 'single' else "Múltiplos"; st.markdown(f"**Upload:** `{sub}`")
        if st.session_state.app_mode is not None:
            if st.button("Voltar ao Menu Principal"): reset_to_main_menu(); st.rerun()
        st.markdown("---"); st.caption("Repo: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agent)") # Atualize

# --- ROTEAMENTO PRINCIPAL ---

# 1. TELA INICIAL (Sem mudanças)
if st.session_state.app_mode is None:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    col_logo, col_title = st.columns([1, 3]);
    with col_logo: st.image("assets/logo_meta_singularity.png", width=250)
    with col_title: st.title("Bem-vindo..."); st.header("Extração Inteligente de NF")
    st.markdown("---"); st.subheader("Selecione uma opção:")
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True): st.markdown("### 1. Arquivo Único"); st.markdown("Gere um Excel por nota.")
        if st.button("Processar Único", use_container_width=True, type="primary", key="btn_single_mode"): st.session_state.app_mode = "single"; st.session_state.compiled_upload_method = None; st.rerun()
    with col2:
        with st.container(border=True): st.markdown("### 2. Compilado"); st.markdown("Acumule em um Excel.")
        if st.button("Processar Compilado", use_container_width=True, type="primary", key="btn_compiled_mode"): st.session_state.app_mode = "accumulated"; st.session_state.compiled_upload_method = None; st.rerun()
    with col3:
        with st.container(border=True): st.markdown("### 3. Guia API"); st.markdown("Aprenda a integrar.")
        if st.button("Abrir Guia Interativo", use_container_width=True, type="primary", key="btn_rag_mode"): st.session_state.app_mode = "rag_chatbot"; st.session_state.compiled_upload_method = None; st.rerun()

# 2. MODO ARQUIVO ÚNICO (Sem mudanças)
elif st.session_state.app_mode == "single":
    render_sidebar(); st.header(f"Chat - Modo: Arquivo Único"); render_chat_history(chat_type="agent")
    if st.session_state.file_just_processed:
        st.info("Concluído.");
        if st.button("Subir Novo", use_container_width=True, type="primary", key="reset_single"): st.session_state.file_just_processed = False; st.rerun()
    else:
        uploaded_file_widget = st.file_uploader("Upload NF:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_single")
        if uploaded_file_widget is not None:
            st.session_state.file_just_processed = True
            uploaded_file = uploaded_file_widget; temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
            with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
            prompt_tecnico = f"Processar: {temp_file_path}"; prompt_bonito = f"Processando: `{uploaded_file.name}`"
            st.session_state.messages.append({"role": "user", "content": prompt_bonito})
            with st.chat_message("user"): st.markdown(prompt_bonito)
            with st.chat_message("assistant"):
                with st.spinner("Agente pensando... 🧠"):
                    estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "single"}
                    if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                    final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config)
                    response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                    st.markdown(response_content)
                    st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
            st.rerun()

# 3. MODO COMPILADO (Sem mudanças)
elif st.session_state.app_mode == "accumulated":
    render_sidebar()
    # 3.1 ESCOLHA DO MÉTODO
    if st.session_state.compiled_upload_method is None:
        st.header("Modo Compilado - Escolha o Método");
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True): st.markdown("#### A. Múltiplos"); st.markdown("Vários de uma vez.")
            if st.button("Selecionar Múltiplos", use_container_width=True, key="btn_multi_select"): st.session_state.compiled_upload_method = 'multiple'; st.session_state.file_just_processed = False; st.rerun()
        with col2:
            with st.container(border=True): st.markdown("#### B. Individual"); st.markdown("Um por vez.")
            if st.button("Subir Individualmente", use_container_width=True, key="btn_single_select"): st.session_state.compiled_upload_method = 'single'; st.session_state.file_just_processed = False; st.rerun()

    # 3.2 MÉTODO: INDIVIDUAL
    elif st.session_state.compiled_upload_method == 'single':
        st.header(f"Chat - Modo: Compilado (Individual)"); render_chat_history(chat_type="agent")
        if st.session_state.file_just_processed:
            st.info("Dados acumulados.");
            if st.button("Subir Próximo", use_container_width=True, type="primary", key="reset_compiled_single"): st.session_state.file_just_processed = False; st.rerun()
        else:
            uploaded_file_widget = st.file_uploader("Upload próximo:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_compiled_single")
            if uploaded_file_widget is not None:
                st.session_state.file_just_processed = True
                uploaded_file = uploaded_file_widget; temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
                with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                prompt_tecnico = f"Processar: {temp_file_path}"; prompt_bonito = f"Acumulando: `{uploaded_file.name}`"
                st.session_state.messages.append({"role": "user", "content": prompt_bonito})
                with st.chat_message("user"): st.markdown(prompt_bonito)
                with st.chat_message("assistant"):
                    with st.spinner("Agente acumulando... 🧠"):
                        estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "accumulated"}
                        if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                        final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config)
                        response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                        st.markdown(response_content)
                        st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
                st.rerun()

    # 3.3 MÉTODO: MÚLTIPLO
    elif st.session_state.compiled_upload_method == 'multiple':
        st.header(f"Chat - Modo: Compilado (Múltiplos)"); render_chat_history(chat_type="agent")
        if st.session_state.file_just_processed:
            st.success("Arquivos processados!");
            if st.button("Subir Novo Lote", use_container_width=True, type="primary", key="reset_compiled_multiple"): st.session_state.file_just_processed = False; st.rerun()
        else:
            uploaded_files_widget = st.file_uploader("Selecione múltiplos arquivos:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key="uploader_compiled_multiple")
            if uploaded_files_widget:
                st.session_state.file_just_processed = True
                total_files = len(uploaded_files_widget); st.info(f"Processando {total_files} arquivos...")
                progress_bar = st.progress(0, text="Iniciando...")
                last_excel_path = None
                if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                for i, uploaded_file in enumerate(uploaded_files_widget):
                    file_name = uploaded_file.name; progress_text = f"Processando {i+1}/{total_files}: {file_name}"
                    progress_bar.progress((i + 1) / total_files, text=progress_text)
                    temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file_name}")
                    with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    prompt_bonito = f"Acumulando ({i+1}/{total_files}): `{file_name}`"
                    st.session_state.messages.append({"role": "user", "content": prompt_bonito})
                    with st.chat_message("user"): st.markdown(prompt_bonito)
                    with st.chat_message("assistant"):
                        with st.spinner(f"Analisando {file_name}..."):
                             prompt_tecnico = f"Processar: {temp_file_path}"
                             estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "accumulated"}
                             final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config)
                             response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                             last_excel_path = excel_path_final
                             st.markdown(response_content)
                             st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
                    time.sleep(0.1)
                progress_bar.empty()
                st.session_state.messages.append({"role": "assistant", "content": f"Processamento de {total_files} arquivos concluído.", "excel_path": last_excel_path})
                st.rerun()

# --- MUDANÇA CRUCIAL: Seção RAG Aprimorada ---
# 4. MODO CHATBOT GUIA API (RAG)
elif st.session_state.app_mode == "rag_chatbot":
    render_sidebar()
    st.header("Guia Interativo e Documentação da API")
    
    st.markdown("""
    Esta seção ajuda você a integrar nosso Agente Extrator de NF em seus próprios sistemas usando nossa API pública. 
    Abaixo você encontra a URL da API e um link para a documentação interativa (Swagger UI), onde você pode 
    testar os endpoints diretamente.
    """)
    
    st.warning("**Recomendamos verificar a documentação antes de usar o chat para economizar tokens.**", icon="💡")

    # Informações da API
    api_url = "https://meta-singularity-api-nf-agente.onrender.com" # Sua URL pública
    docs_url = f"{api_url}/docs"

    st.subheader("URL da API:")
    st.code(f"{api_url}/processar_nf/", language=None)
    
    st.link_button("Acessar Documentação Interativa e Testes (Swagger UI) ↗️", docs_url)
    
    st.markdown("---")
    st.subheader("Assistente de Integração (Chatbot RAG)")
    st.caption("Se tiver dúvidas específicas após consultar a documentação, pergunte abaixo!")

    # Inicializa a pipeline RAG
    if not st.session_state.rag_initialized:
        with st.spinner("Preparando assistente... 🤖"): st.session_state.rag_chain = initialize_rag_pipeline()
    
    # Renderiza histórico do chat RAG
    render_chat_history(chat_type="rag")

    # Input do usuário para o chat RAG
    if prompt := st.chat_input("Pergunte sobre a API (ex: 'Qual o formato da resposta?')"):
        st.session_state.rag_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            if st.session_state.rag_chain:
                with st.spinner("Buscando informações..."):
                    response = st.session_state.rag_chain.invoke(prompt)
                    st.markdown(response)
                    st.session_state.rag_messages.append({"role": "assistant", "content": response})
            else:
                st.error("Assistente RAG não inicializado."); st.session_state.rag_messages.append({"role": "assistant", "content": "Não consigo responder."})