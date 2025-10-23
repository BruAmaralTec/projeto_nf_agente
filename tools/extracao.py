import pandas as pd
from lxml import etree
import pytesseract
import cv2  # OpenCV
from langchain.tools import tool
from PIL import Image
import os
import tempfile
from typing import Optional

# Novas importações
from pdf2image import convert_from_path
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

# --- Configuração (Necessário para Windows) ---
poppler_path = None # Deixe None se estiver no PATH

# --- MUDANÇA CRUCIAL: O "MOLDE" DE DADOS FOI EXPANDIDO ---
class DadosNotaFiscal(BaseModel):
    """
    Estrutura de dados para armazenar informações extraídas de uma nota fiscal.
    Todos os campos são opcionais e serão preenchidos se encontrados.
    """
    # Dados Principais
    chave_acesso: Optional[str] = Field(description="Número da Chave de Acesso da NF-e (44 dígitos) ou Código de Verificação da NFS-e")
    numero_nf: Optional[str] = Field(description="Número da Nota Fiscal (ex: 'Número: 1254200' ou 'Nº 255376898')")
    data_emissao: Optional[str] = Field(description="Data e Hora de Emissão da nota (ex: '20/09/2025 19:51:09' ou '19/10/2025 22:32:33')")
    
    # Dados do Emitente (Quem Vendeu)
    cnpj_emitente: Optional[str] = Field(description="CNPJ do emissor da nota fiscal")
    nome_emitente: Optional[str] = Field(description="Nome ou Razão Social do emissor")
    endereco_emitente: Optional[str] = Field(description="Endereço completo (Rua, N°, Bairro) do emissor")
    municipio_emitente: Optional[str] = Field(description="Município e UF do emissor (ex: 'São Paulo UF: SP')")

    # Dados do Destinatário (Quem Comprou)
    cnpj_cpf_destinatario: Optional[str] = Field(description="CNPJ ou CPF do destinatário/tomador")
    nome_destinatario: Optional[str] = Field(description="Nome ou Razão Social do destinatário/tomador")
    endereco_destinatario: Optional[str] = Field(description="Endereço completo (Rua, N°, Bairro) do destinatário")
    municipio_destinatario: Optional[str] = Field(description="Município e UF do destinatário (ex: 'São Paulo UF: SP')")

    # Valores
    valor_total: Optional[float] = Field(description="Valor Total da nota fiscal (ex: 'Valor a pagar R$: 138,95' ou 'VALOR TOTAL DO SERVIÇO = R$ 238,36')")
    base_calculo: Optional[float] = Field(description="Valor da Base de Cálculo do ISS ou ICMS")
    valor_iss: Optional[float] = Field(description="Valor do ISS (imposto sobre serviço)")
    valor_icms: Optional[float] = Field(description="Valor do ICMS (imposto sobre mercadoria)")

    # Detalhes (NF de Serviço)
    discriminacao_servicos: Optional[str] = Field(description="Texto que descreve os serviços prestados (ex: 'licenciamento ou direito de uso de programa de computador')")


# --- Ferramentas de Extração (Com @tool) ---
# ... (as 4 ferramentas de extração: xml, imagem, pdf, html permanecem IDÊNTICAS) ...
@tool
def extrair_dados_xml(caminho_do_arquivo_xml: str) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Usando Ferramenta de Extração de XML ---")
    try:
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        tree = etree.parse(caminho_do_arquivo_xml); root = tree.getroot(); dados_nf = {}
        chave_node = root.find('.//nfe:infNFe', ns);
        if chave_node is not None: dados_nf['Chave de Acesso'] = chave_node.get('Id').replace('NFe', '')
        cnpj_emitente_node = root.find('.//nfe:emit/nfe:CNPJ', ns);
        if cnpj_emitente_node is not None: dados_nf['CNPJ Emitente'] = cnpj_emitente_node.text
        nome_emitente_node = root.find('.//nfe:emit/nfe:xNome', ns);
        if nome_emitente_node is not None: dados_nf['Nome Emitente'] = nome_emitente_node.text
        cnpj_dest_node = root.find('.//nfe:dest/nfe:CNPJ', ns); cpf_dest_node = root.find('.//nfe:dest/nfe:CPF', ns)
        if cnpj_dest_node is not None: dados_nf['CNPJ/CPF Destinatario'] = cnpj_dest_node.text
        elif cpf_dest_node is not None: dados_nf['CNPJ/CPF Destinatario'] = cpf_dest_node.text
        nome_dest_node = root.find('.//nfe:dest/nfe:xNome', ns);
        if nome_dest_node is not None: dados_nf['Nome Destinatario'] = nome_dest_node.text
        valor_total_node = root.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns);
        if valor_total_node is not None: dados_nf['Valor Total NF'] = float(valor_total_node.text)
        resultado_formatado = "\n".join([f"{chave}: {valor}" for chave, valor in dados_nf.items()])
        if not resultado_formatado: return "Não foi possível extrair dados estruturados do XML."
        print("Dados do XML extraídos com sucesso!"); return resultado_formatado
    except Exception as e:
        print(f"Erro ao processar XML: {e}"); return f"Erro ao processar o arquivo XML: {e}"

@tool
def extrair_texto_imagem(caminho_do_arquivo_imagem: str) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Usando Ferramenta de Extração de Imagem (OCR) ---")
    try:
        img = cv2.imread(caminho_do_arquivo_imagem)
        img_cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        texto_extraido = pytesseract.image_to_string(img_cinza, lang='por')
        if not texto_extraido: return "Nenhum texto encontrado na imagem."
        print("Texto da imagem extraído com sucesso!"); return texto_extraido
    except Exception as e:
        print(f"Erro ao processar imagem: {e}"); return f"Erro ao processar o arquivo de imagem: {e}."

@tool
def extrair_texto_pdf(caminho_do_arquivo_pdf: str) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Usando Ferramenta de Extração de PDF (OCR) ---")
    with tempfile.TemporaryDirectory() as path_temporario:
        try:
            imagens_pdf = convert_from_path(caminho_do_arquivo_pdf, poppler_path=poppler_path)
            texto_completo = ""
            for i, imagem in enumerate(imagens_pdf):
                print(f"Processando página {i+1} do PDF...")
                caminho_img_temp = os.path.join(path_temporario, f"pagina_{i}.png")
                imagem.save(caminho_img_temp, "PNG")
                img_cv = cv2.imread(caminho_img_temp)
                img_cinza = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                texto_pagina = pytesseract.image_to_string(img_cinza, lang='por')
                texto_completo += f"\n--- Página {i+1} ---\n" + texto_pagina
            if not texto_completo: return "Nenhum texto encontrado no PDF."
            print("Texto do PDF extraído com sucesso!"); return texto_completo
        except Exception as e:
            print(f"Erro ao processar PDF: {e}"); return f"Erro ao processar o arquivo PDF: {e}."

@tool
def extrair_texto_html(caminho_do_arquivo_html: str) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Usando Ferramenta de Extração de HTML ---")
    try:
        conteudo = "";
        try:
            with open(caminho_do_arquivo_html, 'r', encoding='utf-8') as f: conteudo = f.read()
        except UnicodeDecodeError:
            print("UTF-8 falhou, tentando latin-1...");
            with open(caminho_do_arquivo_html, 'r', encoding='latin-1') as f: conteudo = f.read()
        if not conteudo: return "Arquivo HTML vazio ou não pôde ser lido."
        soup = BeautifulSoup(conteudo, 'lxml');
        for script_ou_style in soup(["script", "style"]): script_ou_style.decompose()
        texto = soup.body.get_text();
        linhas = (line.strip() for line in texto.splitlines())
        partes = (frase.strip() for linha in linhas for frase in linha.split("  "))
        texto_limpo = '\n'.join(p for p in partes if p)
        if not texto_limpo: return "Nenhum texto visível encontrado no arquivo HTML."
        print("Texto do HTML extraído com sucesso!"); return texto_limpo
    except Exception as e:
        print(f"Erro ao processar HTML: {e}"); return f"Erro ao processar o arquivo HTML: {e}"

# --- Ferramenta Genérica de Salvamento (Sem mudança) ---
@tool
def salvar_dados_nota(dados_nota: DadosNotaFiscal) -> str:
    """
    Ferramenta GENÉRICA de salvamento. O Agente DEVE chamar esta ferramenta
    depois de extrair os dados da nota.
    O sistema interno irá decidir se salva em um arquivo único ou acumulado.
    Recebe os dados no formato 'DadosNotaFiscal'.
    Retorna uma string de confirmação.
    """
    print(f"--- Ferramenta 'salvar_dados_nota' chamada pelo Agente ---")
    return "Chamada de salvamento recebida."


# --- Funções de Lógica Interna de Salvamento (Sem mudança) ---
# Elas automaticamente usarão o "molde" expandido de DadosNotaFiscal

def salvar_dados_em_excel(dados_nota: DadosNotaFiscal) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Lógica Interna: Salvamento (ÚNICO) ---")
    try:
        output_dir = "dados_saida"
        os.makedirs(output_dir, exist_ok=True)
        dados_dict = dados_nota.model_dump(); df = pd.DataFrame([dados_dict])
        chave_limpa = dados_dict.get('chave_acesso', 'sem_chave');
        if not chave_limpa: chave_limpa = 'sem_chave'
        nome_arquivo = f"nota_{chave_limpa.replace(' ', '_')}.xlsx"
        caminho_completo = os.path.join(output_dir, nome_arquivo)
        df.to_excel(caminho_completo, index=False)
        print(f"Dados salvos com sucesso em: {caminho_completo}")
        return caminho_completo
    except Exception as e:
        print(f"Erro ao salvar arquivo Excel: {e}"); return f"Erro ao salvar: {e}"

def acumular_dados_em_excel(dados_nota: DadosNotaFiscal) -> str:
    # ... (código interno sem mudança) ...
    print(f"--- Lógica Interna: Salvamento (COMPILADO) ---")
    try:
        output_dir = "dados_saida"
        os.makedirs(output_dir, exist_ok=True)
        caminho_arquivo_mestre = os.path.join(output_dir, "COMPILADO_MESTRE.xlsx")
        dados_dict = dados_nota.model_dump(); novo_df = pd.DataFrame([dados_dict])
        
        if os.path.exists(caminho_arquivo_mestre):
            print("Arquivo mestre encontrado. Lendo dados existentes...")
            df_existente = pd.read_excel(caminho_arquivo_mestre)
            df_combinado = pd.concat([df_existente, novo_df], ignore_index=True)
            df_combinado.to_excel(caminho_arquivo_mestre, index=False)
            print("Dados adicionados ao arquivo mestre com sucesso.")
        else:
            print("Arquivo mestre não encontrado. Criando novo arquivo...")
            novo_df.to_excel(caminho_arquivo_mestre, index=False)
            print("Novo arquivo mestre criado com sucesso.")
        return caminho_arquivo_mestre
    except Exception as e:
        print(f"Erro ao acumular dados no Excel: {e}"); return f"Erro ao acumular: {e}"