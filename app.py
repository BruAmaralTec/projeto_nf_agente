import streamlit as st
import os
import uuid
from workflows.graph import app as langgraph_app # Renomeado para clareza
from langchain_core.messages import HumanMessage
import time

# --- Novas Importações para RAG ---
from langchain_community.document_loaders import MarkdownLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# Carrega a chave da API (necessária para Embeddings e LLM do RAG)
load_dotenv()

# --- CSS (Sem mudanças) ---
NOVA_COR_PRIMARIA = "#C0FF72"; NOVA_COR_SECUNDARIA = "#A9E64B"; NOVA_COR_HOVER = "#98CC42"; TEXTO_COR = "#000000"
st.markdown(f"""<style>[data-testid="stSidebar"] {{ background-color: {NOVA_COR_PRIMARIA}; color: {TEXTO_COR}; }}[data-testid="stSidebar"] .st-emotion-cache-1pxjwj4 {{ color: {TEXTO_COR}; }}.st-emotion-cache-10qj7k0, [data-testid="stButton"] button {{ background-color: {NOVA_COR_SECUNDARIA} !important; color: {TEXTO_COR} !important; border: 1px solid {NOVA_COR_HOVER}; }}.st-emotion-cache-10qj7k0:hover, [data-testid="stButton"] button:hover {{ background-color: {NOVA_COR_HOVER} !important; border: 1px solid {NOVA_COR_HOVER}; }}.st-emotion-cache-7ym5gk {{ transition: transform 0.1s ease-in-out; }}.st-emotion-cache-7ym5gk:hover {{ transform: scale(1.02); }}</style>""", unsafe_allow_html=True)

# --- Configuração da Página (Sem mudanças) ---
st.set_page_config(page_title="Meta Singularity - Agente NF", page_icon="assets/logo_meta_singularity.png", layout="wide", initial_sidebar_state="auto")

# --- Diretórios (Sem mudanças) ---
UPLOAD_DIR = "dados_upload"; OUTPUT_DIR = "dados_saida"
os.makedirs(UPLOAD_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
DOCS_PATH = "docs/system_guide.md" # Caminho para o guia

# --- Gerenciamento de Estado Principal ---
if "app_mode" not in st.session_state: st.session_state.app_mode = None
if "compiled_upload_method" not in st.session_state: st.session_state.compiled_upload_method = None 
if "file_just_processed" not in st.session_state: st.session_state.file_just_processed = False
# --- MUDANÇA: Novo estado para o chat de ajuda ---
if "help_messages" not in st.session_state: st.session_state.help_messages = []

# --- Funções Auxiliares ---
def reset_to_main_menu():
    """Reseta todos os estados para voltar à tela inicial."""
    st.session_state.app_mode = None
    st.session_state.compiled_upload_method = None
    st.session_state.messages = [] # Limpa chat principal
    st.session_state.help_messages = [] # Limpa chat de ajuda
    st.session_state.file_just_processed = False
    
def render_chat_history(message_list_key="messages"): # Chave para diferenciar históricos
    """Desenha o histórico do chat especificado e os botões de download."""
    if message_list_key not in st.session_state: st.session_state[message_list_key] = []
    for i, message in enumerate(st.session_state[message_list_key]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Botão de download só para o chat principal
            if message_list_key == "messages" and message["role"] == "assistant" and "excel_path" in message:
                excel_path = message["excel_path"]
                if excel_path and os.path.exists(excel_path):
                    with open(excel_path, "rb") as f:
                        st.download_button(
                            label=f"Download {os.path.basename(excel_path)}", data=f, file_name=os.path.basename(excel_path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"history_btn_{st.session_state.app_mode or 'none'}_{st.session_state.compiled_upload_method or 'none'}_{i}"
                        )

def render_sidebar():
    """Desenha a barra lateral padrão."""
    with st.sidebar:
        st.image("assets/logo_meta_singularity.png", width=200)
        st.title("Meta Singularity")
        st.header("🤖 Agente Extrator de NF")
        st.markdown("---")
        
        modo_atual_display = "Nenhum (Tela Inicial)"
        if st.session_state.app_mode == "single": modo_atual_display = "Arquivo Único"
        elif st.session_state.app_mode == "accumulated": modo_atual_display = "Compilado"
        elif st.session_state.app_mode == "help": modo_atual_display = "Guia Interativo"
        
        st.markdown(f"**Modo Atual:** `{modo_atual_display}`")
        if st.session_state.app_mode == "accumulated" and st.session_state.compiled_upload_method:
             sub_modo = "Individual" if st.session_state.compiled_upload_method == 'single' else "Múltiplos Arquivos"
             st.markdown(f"**Método Upload:** `{sub_modo}`")

        # Botão sempre visível, exceto na tela inicial
        if st.session_state.app_mode is not None:
            if st.button("Voltar ao Menu Principal"):
                reset_to_main_menu()
                st.rerun() 
            st.markdown("---")
            
        st.caption("Repositório do Projeto: [GitHub](https://github.com/BruAmaralTec/projeto_nf_agent)") 

# --- LÓGICA RAG (CACHEADA) ---
@st.cache_resource # Cacheia o pipeline RAG inteiro
def load_rag_pipeline(doc_path=DOCS_PATH):
    """Carrega o documento, cria o vector store e o pipeline RAG."""
    if not os.path.exists(doc_path):
        st.error(f"Arquivo de documentação não encontrado em: {doc_path}")
        return None
        
    try:
        # 1. Carregar o Documento
        loader = MarkdownLoader(doc_path)
        docs = loader.load()

        # 2. Dividir em Chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
        # Verifica se a chave da API está disponível para Embeddings
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Chave da API OpenAI não encontrada. Verifique o arquivo .env ou os Secrets do Streamlit.")
            return None

        # 3. Criar Vector Store (FAISS)
        vectorstore = FAISS.from_documents(documents=splits, embedding=OpenAIEmbeddings())

        # 4. Criar Retriever
        retriever = vectorstore.as_retriever()

        # 5. Definir Prompt Template
        template = """Você é um assistente prestativo. Responda à pergunta do usuário baseado APENAS no contexto fornecido.
        Se a informação não estiver no contexto, diga que você não sabe. Seja conciso.

        Contexto:
        {context}

        Pergunta: 
        {question}

        Resposta:"""
        prompt = ChatPromptTemplate.from_template(template)

        # 6. Definir LLM
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 7. Criar a Cadeia RAG
        rag_chain_from_docs = (
            RunnablePassthrough.assign(context=(lambda x: x["question"]) | retriever)
            | prompt
            | llm
            | StrOutputParser()
        )
        
        # Alternativa mais simples para passar a pergunta e o contexto
        rag_chain = RunnableParallel(
             {"context": retriever, "question": RunnablePassthrough()}
        ) | prompt | llm | StrOutputParser()


        print("Pipeline RAG carregado com sucesso.")
        return rag_chain

    except Exception as e:
        st.error(f"Erro ao carregar o pipeline RAG: {e}")
        return None

# Carrega o pipeline uma vez (ou pega do cache)
rag_pipeline = load_rag_pipeline()

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
    
    # --- MUDANÇA: Layout de 3 colunas ---
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 1. Arquivo Único")
            st.markdown("Gere um Excel separado para cada nota.")
            if st.button("Iniciar Único", use_container_width=True, type="primary", key="btn_single_mode"):
                st.session_state.app_mode = "single"; st.rerun() 
    with col2:
        with st.container(border=True):
            st.markdown("### 2. Compilado")
            st.markdown("Acumule dados em um único Excel.")
            if st.button("Iniciar Compilado", use_container_width=True, type="primary", key="btn_compiled_mode"):
                st.session_state.app_mode = "accumulated"; st.session_state.compiled_upload_method = None; st.rerun() 
    # --- MUDANÇA: Nova coluna e botão ---
    with col3:
        with st.container(border=True):
            st.markdown("### 3. Guia / Ajuda")
            st.markdown("Pergunte sobre como usar o sistema ou a API.")
            if st.button("Abrir Guia Interativo", use_container_width=True, type="secondary", key="btn_help_mode"):
                st.session_state.app_mode = "help"; st.rerun() 

# 2. MODO ARQUIVO ÚNICO (Interface de Chat Normal)
elif st.session_state.app_mode == "single":
    render_sidebar()
    st.header(f"Chat de Processamento - Modo: Arquivo Único")
    render_chat_history("messages")
    if st.session_state.file_just_processed:
        st.info("Processamento concluído.")
        if st.button("Subir Novo Arquivo", use_container_width=True, type="primary", key="reset_single"):
            st.session_state.file_just_processed = False; st.rerun()
    else:
        uploaded_file_widget = st.file_uploader("Upload NF:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_single")
        if uploaded_file_widget is not None:
            st.session_state.file_just_processed = True
            uploaded_file = uploaded_file_widget ; temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
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

# 3. MODO COMPILADO
elif st.session_state.app_mode == "accumulated":
    render_sidebar()
    # 3.1 TELA DE ESCOLHA COMPILADO
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
                st.markdown("#### B. Um Arquivo por Vez"); st.markdown("Suba um arquivo, veja resultado, suba o próximo.")
                if st.button("Subir Individualmente", use_container_width=True, key="btn_single_select"):
                    st.session_state.compiled_upload_method = 'single'; st.session_state.file_just_processed = False; st.rerun()
    # 3.2 COMPILADO INDIVIDUAL (Chat)
    elif st.session_state.compiled_upload_method == 'single':
        st.header(f"Chat - Modo: Compilado (Individual)")
        render_chat_history("messages")
        if st.session_state.file_just_processed:
            st.info("Dados acumulados no arquivo mestre.")
            if st.button("Subir Próximo Arquivo", use_container_width=True, type="primary", key="reset_compiled_single"):
                st.session_state.file_just_processed = False; st.rerun()
        else:
            uploaded_file_widget = st.file_uploader("Upload próximo arquivo:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], label_visibility="collapsed", key="uploader_compiled_single")
            if uploaded_file_widget is not None:
                st.session_state.file_just_processed = True
                uploaded_file = uploaded_file_widget ; temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{uploaded_file.name}")
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
    # 3.3 COMPILADO MÚLTIPLO
    elif st.session_state.compiled_upload_method == 'multiple':
        st.header(f"Chat - Modo: Compilado (Múltiplos Arquivos)")
        render_chat_history("messages")
        if st.session_state.file_just_processed:
            st.success("Arquivos processados! Dados acumulados no arquivo mestre.")
            if st.button("Subir Novo Lote", use_container_width=True, type="primary", key="reset_compiled_multiple"):
                st.session_state.file_just_processed = False; st.rerun()
        else:
            uploaded_files_widget = st.file_uploader("Selecione múltiplos arquivos:", type=["pdf", "xml", "html", "png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key="uploader_compiled_multiple")
            if uploaded_files_widget:
                st.session_state.file_just_processed = True; total_files = len(uploaded_files_widget)
                st.info(f"Processando {total_files} arquivos...")
                progress_bar = st.progress(0, text="Iniciando..."); last_excel_path = None 
                if "thread_config" not in st.session_state: st.session_state.thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                for i, uploaded_file in enumerate(uploaded_files_widget):
                    file_name = uploaded_file.name; progress_text = f"Processando {i+1}/{total_files}: {file_name}"; progress_bar.progress((i + 1) / total_files, text=progress_text)
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
                    time.sleep(0.5)
                progress_bar.empty()
                st.session_state.messages.append({"role": "assistant", "content": f"Processamento de {total_files} arquivos concluído.", "excel_path": last_excel_path})
                st.rerun() 

# --- MUDANÇA: 4. MODO GUIA INTERATIVO ---
elif st.session_state.app_mode == 'help':
    render_sidebar() # Mostra a sidebar
    st.header("Guia Interativo / Ajuda do Sistema")
    st.markdown("Faça uma pergunta sobre como usar o sistema, a API, ou solucionar problemas.")

    # Renderiza o histórico do chat de ajuda
    render_chat_history("help_messages") # Usa a chave 'help_messages'

    # Chat Input para o Guia
    prompt = st.chat_input("Pergunte sobre o sistema...")

    if prompt:
        # Adiciona a pergunta do usuário ao histórico de ajuda
        st.session_state.help_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Chama o pipeline RAG (se carregado com sucesso)
        with st.chat_message("assistant"):
            if rag_pipeline:
                with st.spinner("Consultando a base de conhecimento... 🧠"):
                    try:
                        # Invoca a cadeia RAG com a pergunta do usuário
                        response = rag_pipeline.invoke(prompt)
                        st.markdown(response)
                        # Adiciona a resposta do RAG ao histórico de ajuda
                        st.session_state.help_messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"Desculpe, ocorreu um erro ao consultar a base de conhecimento: {e}"
                        st.error(error_msg)
                        st.session_state.help_messages.append({"role": "assistant", "content": error_msg})
            else:
                # Se o pipeline RAG falhou ao carregar
                error_msg = "Desculpe, o Guia Interativo não está disponível no momento devido a um erro de configuração."
                st.error(error_msg)
                st.session_state.help_messages.append({"role": "assistant", "content": error_msg})
        
        # Não precisa de rerun aqui, o chat atualiza na próxima interação