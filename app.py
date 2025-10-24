import streamlit as st
import os
import uuid
from workflows.graph import app as langgraph_app # Renomeado para clareza
from langchain_core.messages import HumanMessage
import time

# --- Novas Importações para RAG ---
# --- MUDANÇA CRUCIAL AQUI ---
from langchain_community.document_loaders.markdown import MarkdownLoader # Caminho corrigido
# --- FIM DA MUDANÇA ---
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Para a pipeline RAG
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate

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
if "compiled_upload_method" not in st.session_state:
    st.session_state.compiled_upload_method = None
if "file_just_processed" not in st.session_state:
    st.session_state.file_just_processed = False
# Novos estados para o chatbot RAG
if "rag_initialized" not in st.session_state:
    st.session_state.rag_initialized = False
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "rag_messages" not in st.session_state:
    st.session_state.rag_messages = []


# --- Funções Auxiliares ---
def reset_to_main_menu():
    """Reseta todos os estados para voltar à tela inicial."""
    st.session_state.app_mode = None
    st.session_state.compiled_upload_method = None
    st.session_state.messages = [] # Limpa chat do agente
    st.session_state.rag_messages = [] # Limpa chat do RAG
    st.session_state.file_just_processed = False
    # Não resetamos session_id ou thread_config

# --- Funções RAG ---
@st.cache_resource # Cacheia o recurso para não recarregar a cada interação
def initialize_rag_pipeline():
    """Carrega docs, cria embeddings, vector store e a chain RAG."""
    try:
        # 1. Carregar Documento (Assumindo que você criará este arquivo)
        doc_path = "docs/api_guide.md"
        if not os.path.exists(doc_path):
             # Cria um arquivo dummy se não existir
             os.makedirs("docs", exist_ok=True)
             with open(doc_path, "w", encoding="utf-8") as f:
                 f.write("# Guia da API Meta Singularity NF Extract\n\n")
                 f.write("## Endpoint\n\nO endpoint principal é `/processar_nf/`.\n\n")
                 f.write("## Método\n\nUse o método HTTP POST.\n\n")
                 f.write("## Corpo da Requisição\n\nEnvie os dados como `multipart/form-data` contendo:\n")
                 f.write("- `file`: O arquivo da nota fiscal (.pdf, .xml, .png, etc.).\n")
                 f.write("- `mode`: Uma string indicando o modo ('single' ou 'accumulated').\n\n")
                 f.write("## Resposta\n\nA API retornará um JSON com os dados extraídos da nota fiscal.\n")
                 f.write("```json\n{\n  \"chave_acesso\": \"...\",\n  \"numero_nf\": \"...\",\n  ...\n}\n```\n")

        loader = MarkdownLoader(doc_path)
        docs = loader.load()

        # 2. Dividir Documento
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=50)
        splits = text_splitter.split_documents(docs)

        # 3. Embeddings e Vector Store
        embeddings = OpenAIEmbeddings() # Usa a chave da OpenAI dos secrets
        vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)

        # 4. Retriever
        retriever = vectorstore.as_retriever()

        # 5. Prompt RAG
        template = """Você é um assistente prestativo respondendo perguntas sobre como usar a API Meta Singularity NF Extract.
Use APENAS o contexto fornecido abaixo para responder à pergunta. Não invente informações.
Se a resposta não estiver no contexto, diga que você não tem essa informação.

Contexto:
{context}

Pergunta: {question}

Resposta:"""
        prompt = ChatPromptTemplate.from_template(template)

        # 6. LLM (Reutiliza a chave dos secrets)
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 7. Chain RAG
        rag_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        st.session_state.rag_initialized = True
        return rag_chain

    except Exception as e:
        st.error(f"Erro ao inicializar o chatbot RAG: {e}")
        st.session_state.rag_initialized = False
        return None

# --- Funções de Renderização ---
def render_chat_history(chat_type="agent"):
    """Desenha o histórico do chat especificado."""
    messages_key = "messages" if chat_type == "agent" else "rag_messages"
    if messages_key not in st.session_state: st.session_state[messages_key] = []

    for i, message in enumerate(st.session_state[messages_key]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Botão de download apenas para o chat do agente
            if chat_type == "agent" and message["role"] == "assistant" and "excel_path" in message:
                excel_path = message["excel_path"]
                if excel_path and os.path.exists(excel_path):
                    with open(excel_path, "rb") as f:
                        st.download_button(
                            label=f"Download {os.path.basename(excel_path)}",
                            data=f,
                            file_name=os.path.basename(excel_path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"history_btn_{st.session_state.app_mode}_{st.session_state.compiled_upload_method}_{i}"
                        )

def render_sidebar():
    """Desenha a barra lateral."""
    with st.sidebar:
        st.image("assets/logo_meta_singularity.png", width=200)
        st.title("Meta Singularity")
        st.header("🤖 Agente Extrator de NF")
        st.markdown("---")
        
        # Botão para Chatbot Guia API
        if st.button("Guia Interativo da API", key="btn_goto_rag"):
             st.session_state.app_mode = "rag_chatbot"
             st.session_state.compiled_upload_method = None
             st.session_state.file_just_processed = False
             # Não limpa mensagens aqui, pode querer voltar
             st.rerun()

        st.markdown("---")
        
        if st.session_state.app_mode not in [None, "rag_chatbot"]:
            modo_atual = "Arquivo Único" if st.session_state.app_mode == "single" else "Compilado"
            st.markdown(f"**Modo Atual:** `{modo_atual}`")
            if st.session_state.compiled_upload_method:
                 sub_modo = "Individual" if st.session_state.compiled_upload_method == 'single' else "Múltiplos Arquivos"
                 st.markdown(f"**Método Upload:** `{sub_modo}`")

        if st.session_state.app_mode != None: # Mostra se não estiver na tela inicial
            if st.button("Voltar ao Menu Principal"):
                reset_to_main_menu()
                st.rerun() 
            
        st.markdown("---")
        st.caption("Repositório do Projeto: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agent)") # Atualize se necessário

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
    st.subheader("Por favor, selecione uma opção:")
    col1, col2, col3 = st.columns(3) # Adicionada terceira coluna
    with col1:
        with st.container(border=True):
            st.markdown("### 1. Modo: Arquivo Único")
            st.markdown("Gere um Excel separado para cada nota.")
            if st.button("Processamento Único", use_container_width=True, type="primary", key="btn_single_mode"):
                st.session_state.app_mode = "single"; st.session_state.compiled_upload_method = None; st.rerun() 
    with col2:
        with st.container(border=True):
            st.markdown("### 2. Modo: Compilado")
            st.markdown("Acumule dados de várias notas em um Excel.")
            if st.button("Processamento Compilado", use_container_width=True, type="primary", key="btn_compiled_mode"):
                st.session_state.app_mode = "accumulated"; st.session_state.compiled_upload_method = None; st.rerun() 
    with col3: # Nova coluna para o Guia API
        with st.container(border=True):
            st.markdown("### 3. Guia da API")
            st.markdown("Converse com um chatbot para aprender a integrar.")
            if st.button("Abrir Guia Interativo", use_container_width=True, type="primary", key="btn_rag_mode"):
                st.session_state.app_mode = "rag_chatbot"; st.session_state.compiled_upload_method = None; st.rerun()

# 2. MODO ARQUIVO ÚNICO
elif st.session_state.app_mode == "single":
    render_sidebar()
    st.header(f"Chat de Processamento - Modo: Arquivo Único")
    render_chat_history(chat_type="agent")

    if st.session_state.file_just_processed:
        st.info("Processamento concluído.")
        if st.button("Subir Novo Arquivo", use_container_width=True, type="primary", key="reset_single"):
            st.session_state.file_just_processed = False; st.rerun()
    else:
        uploaded_file_widget = st.file_uploader("Upload NF:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_single")
        if uploaded_file_widget is not None:
            st.session_state.file_just_processed = True
            uploaded_file = uploaded_file_widget 
            temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
            with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
            prompt_tecnico = f"Processar: {temp_file_path}"; prompt_bonito = f"Processando: `{uploaded_file.name}`"
            st.session_state.messages.append({"role": "user", "content": prompt_bonito})
            with st.chat_message("user"): st.markdown(prompt_bonito)
            with st.chat_message("assistant"):
                with st.spinner("Agente pensando... 🧠"):
                    estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "single"}
                    if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                    final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config) # Usando nome renomeado
                    response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                    st.markdown(response_content)
                    st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
            st.rerun()

# 3. MODO COMPILADO
elif st.session_state.app_mode == "accumulated":
    render_sidebar() 
    # 3.1 ESCOLHA DO MÉTODO
    if st.session_state.compiled_upload_method is None:
        st.header("Modo Compilado - Escolha o Método")
        col1, col2 = st.columns(2)
        with col1:
             with st.container(border=True):
                 st.markdown("#### A. Múltiplos Arquivos"); st.markdown("Selecione vários arquivos de uma vez.")
                 if st.button("Selecionar Múltiplos", use_container_width=True, key="btn_multi_select"):
                     st.session_state.compiled_upload_method = 'multiple'; st.session_state.file_just_processed = False; st.rerun()
        with col2:
            with st.container(border=True):
                st.markdown("#### B. Um Arquivo por Vez"); st.markdown("Suba arquivos individualmente.")
                if st.button("Subir Individualmente", use_container_width=True, key="btn_single_select"):
                    st.session_state.compiled_upload_method = 'single'; st.session_state.file_just_processed = False; st.rerun()

    # 3.2 MÉTODO: INDIVIDUAL
    elif st.session_state.compiled_upload_method == 'single':
        st.header(f"Chat - Modo: Compilado (Individual)")
        render_chat_history(chat_type="agent")
        if st.session_state.file_just_processed:
            st.info("Dados acumulados no arquivo mestre.")
            if st.button("Subir Próximo", use_container_width=True, type="primary", key="reset_compiled_single"):
                st.session_state.file_just_processed = False; st.rerun()
        else:
            uploaded_file_widget = st.file_uploader("Upload próximo arquivo:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_compiled_single")
            if uploaded_file_widget is not None:
                st.session_state.file_just_processed = True
                uploaded_file = uploaded_file_widget 
                temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
                with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                prompt_tecnico = f"Processar: {temp_file_path}"; prompt_bonito = f"Acumulando: `{uploaded_file.name}`"
                st.session_state.messages.append({"role": "user", "content": prompt_bonito})
                with st.chat_message("user"): st.markdown(prompt_bonito)
                with st.chat_message("assistant"):
                    with st.spinner("Agente acumulando... 🧠"):
                        estado_inicial = {"messages": [HumanMessage(content=prompt_tecnico)], "file_path": temp_file_path, "excel_file_path": None, "app_mode": "accumulated"}
                        if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                        final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config) # Usando nome renomeado
                        response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                        st.markdown(response_content)
                        st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final})
                st.rerun()

    # 3.3 MÉTODO: MÚLTIPLO
    elif st.session_state.compiled_upload_method == 'multiple':
        st.header(f"Chat - Modo: Compilado (Múltiplos)")
        render_chat_history(chat_type="agent")
        if st.session_state.file_just_processed:
            st.success("Arquivos processados! Dados acumulados.")
            if st.button("Subir Novo Lote", use_container_width=True, type="primary", key="reset_compiled_multiple"):
                st.session_state.file_just_processed = False; st.rerun()
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
                             final_state = langgraph_app.invoke(estado_inicial, config=st.session_state.thread_config) # Usando nome renomeado
                             response_message = final_state["messages"][-1]; response_content = response_message.content; excel_path_final = final_state.get("excel_file_path")
                             last_excel_path = excel_path_final
                             st.markdown(response_content)
                             st.session_state.messages.append({"role": "assistant", "content": response_content, "excel_path": excel_path_final}) 
                    time.sleep(0.5) 
                progress_bar.empty() 
                st.session_state.messages.append({"role": "assistant", "content": f"Processamento de {total_files} arquivos concluído.", "excel_path": last_excel_path})
                st.rerun() 

# 4. MODO CHATBOT GUIA API (RAG)
elif st.session_state.app_mode == "rag_chatbot":
    render_sidebar()
    st.header("Guia Interativo da API Meta Singularity")
    st.caption("Faça perguntas sobre como usar nossa API de extração de NF.")

    # Inicializa a pipeline RAG na primeira vez que entra neste modo
    if not st.session_state.rag_initialized:
        with st.spinner("Preparando o assistente da API... 🤖"):
            st.session_state.rag_chain = initialize_rag_pipeline()
    
    # Renderiza histórico do chat RAG
    render_chat_history(chat_type="rag")

    # Input do usuário para o chat RAG
    if prompt := st.chat_input("Pergunte sobre a API..."):
        st.session_state.rag_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if st.session_state.rag_chain:
                with st.spinner("Buscando informações..."):
                    response = st.session_state.rag_chain.invoke(prompt)
                    st.markdown(response)
                    st.session_state.rag_messages.append({"role": "assistant", "content": response})
            else:
                st.error("O assistente RAG não pôde ser inicializado. Verifique os logs.")
                st.session_state.rag_messages.append({"role": "assistant", "content": "Desculpe, não consigo responder agora."})