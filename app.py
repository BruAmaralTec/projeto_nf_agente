import streamlit as st
import os
import uuid
from workflows.graph import app as langgraph_app # Renomeado para clareza
from langchain_core.messages import HumanMessage
import time

# --- Novas Importações para RAG ---
from langchain_community.document_loaders import UnstructuredMarkdownLoader # Mudança para Unstructured
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Para a pipeline RAG
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate

# --- CSS Personalizado ---
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
    body {{
        color: #333333; /* Cor de texto padrão um pouco mais escura */
    }}

    /* --- Barra Lateral --- */
    [data-testid="stSidebar"] {{
        background-color: {NOVA_COR_PRIMARIA_SIDEBAR};
        color: {TEXTO_COR_SIDEBAR};
    }}
    [data-testid="stSidebar"] .st-emotion-cache-1pxjwj4 {{ /* Ajuste seletor se necessário */
        color: {TEXTO_COR_SIDEBAR};
    }}
    /* Link do GitHub na sidebar */
     [data-testid="stSidebar"] .stCaption a {{
         color: #1E88E5 !important; /* Azul para links */
     }}
     [data-testid="stSidebar"] .stCaption a:hover {{
         color: #0D47A1 !important; /* Azul mais escuro no hover */
     }}


    /* --- Botões FORA da Sidebar (Área Principal) --- */
    /* Botões Padrão (Tipo 'secondary' - não usados explicitamente, mas bom definir) */
    .stButton>button:not(:hover) {{
         /* border: 1px solid {COR_BOTAO_PRINCIPAL}; */
         /* background-color: white; */
         /* color: {COR_BOTAO_PRINCIPAL}; */
    }}
    /* Botões Primários (Tipo 'primary' - os verdes que usamos) */
    /* Usar seletor mais genérico que não dependa tanto do cache do emotion */
    [data-testid="stButton"] button[kind="primary"],
    .st-emotion-cache-10qj7k0 /* Seletor antigo como fallback */
    {{
        background-color: {COR_BOTAO_PRINCIPAL} !important;
        color: {TEXTO_COR_SIDEBAR} !important; /* Texto preto combina bem */
        border: 1px solid {COR_BOTAO_HOVER};
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stButton"] button[kind="primary"]:hover,
    .st-emotion-cache-10qj7k0:hover
    {{
        background-color: {COR_BOTAO_HOVER} !important;
        border-color: {COR_BOTAO_HOVER};
        color: {TEXTO_COR_SIDEBAR} !important;
    }}
     /* Botões da tela inicial (animação) */
    .st-emotion-cache-7ym5gk {{ transition: transform 0.1s ease-in-out; }}
    .st-emotion-cache-7ym5gk:hover {{ transform: scale(1.02); }}


    /* --- MUDANÇA CRUCIAL: Botões DENTRO da Sidebar --- */
    [data-testid="stSidebar"] [data-testid="stButton"] button {{
        background-color: {COR_BOTAO_SIDEBAR} !important;
        color: {TEXTO_BOTAO_SIDEBAR} !important;
        border: 1px solid {COR_BOTAO_SIDEBAR_HOVER};
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
        background-color: {COR_BOTAO_SIDEBAR_HOVER} !important;
        border-color: {COR_BOTAO_SIDEBAR_HOVER};
        color: {TEXTO_BOTAO_SIDEBAR} !important;
    }}

    /* Ajuste fino para texto do chat, se necessário */
    [data-testid="stChatMessage"] p {{
        color: #111111;
    }}
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
if "app_mode" not in st.session_state: st.session_state.app_mode = None
if "compiled_upload_method" not in st.session_state: st.session_state.compiled_upload_method = None
if "file_just_processed" not in st.session_state: st.session_state.file_just_processed = False
if "rag_initialized" not in st.session_state: st.session_state.rag_initialized = False
if "rag_chain" not in st.session_state: st.session_state.rag_chain = None
if "rag_messages" not in st.session_state: st.session_state.rag_messages = []


# --- Funções Auxiliares ---
def reset_to_main_menu():
    st.session_state.app_mode = None; st.session_state.compiled_upload_method = None
    st.session_state.messages = []; st.session_state.rag_messages = []
    st.session_state.file_just_processed = False

# --- Funções RAG ---
@st.cache_resource
def initialize_rag_pipeline():
    try:
        doc_path = "docs/api_guide.md"
        if not os.path.exists(doc_path):
             os.makedirs("docs", exist_ok=True)
             with open(doc_path, "w", encoding="utf-8") as f:
                 f.write("# Guia API Meta Singularity NF Extract\n\nEndpoint: `/processar_nf/` (POST)\n\n")
                 f.write("Corpo: `multipart/form-data` com `file` (arquivo NF) e `mode` ('single'/'accumulated').\n\n")
                 f.write("Resposta: JSON com dados extraídos.\n")

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
        st.