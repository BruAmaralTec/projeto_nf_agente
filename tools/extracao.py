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

# --- "MOLDE" DE DADOS EXPANDIDO (v3.0) ---
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

# --- Ferramentas de Extração (COM CORPO COMPLETO E DOCSTRINGS) ---

@tool
def extrair_dados_xml(caminho_do_arquivo_xml: str) -> str:
    """
    Ferramenta especializada em ler um arquivo XML de NF-e (Nota Fiscal Eletrônica).
    Recebe o CAMINHO para o arquivo .xml e extrai os campos principais.
    Retorna uma string formatada com os dados da nota.
    """
    print(f"--- Usando Ferramenta de Extração de XML ---")
    try:
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        tree = etree.parse(caminho_do_arquivo_xml)
        root = tree.getroot()
        dados_nf = {}

        chave_node = root.find('.//nfe:infNFe', ns)
        if chave_node is not None: dados_nf['Chave de Acesso'] = chave_node.get('Id').replace('NFe', '')
        
        cnpj_emitente_node = root.find('.//nfe:emit/nfe:CNPJ', ns)
        if cnpj_emitente_node is not None: dados_nf['CNPJ Emitente'] = cnpj_emitente_node.text

        nome_emitente_node = root.find('.//nfe:emit/nfe:xNome', ns)
        if nome_emitente_node is not None: dados_nf['Nome Emitente'] = nome_emitente_node.text

        cnpj_dest_node = root.find('.//nfe:dest/nfe:CNPJ', ns)
        cpf_dest_node = root.find('.//nfe:dest/nfe:CPF', ns)
        if cnpj_dest_node is not None:
            dados_nf['CNPJ/CPF Destinatario'] = cnpj_dest_node.text
        elif cpf_dest_node is not None:
            dados_nf['CNPJ/CPF Destinatario'] = cpf_dest_node.text

        nome_dest_node = root.find('.//nfe:dest/nfe:xNome', ns)
        if nome_dest_node is not None: dados_nf['Nome Destinatario'] = nome_dest_node.text
        
        valor_total_node = root.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns)
        if valor_total_node is not None: dados_nf['Valor Total NF'] = float(valor_total_node.text)

        resultado_formatado = "\n".join([f"{chave}: {valor}" for chave, valor in dados_nf.items()])
        
        if not resultado_formatado: return "Não foi possível extrair dados estruturados do XML."
        
        print("Dados do XML extraídos com sucesso!")
        return resultado_formatado
    except Exception as e:
        print(f"Erro ao processar XML: {e}"); return f"Erro ao processar o arquivo XML: {e}"

@tool
def extrair_texto_imagem(caminho_do_arquivo_imagem: str) -> str:
    """
    Ferramenta especializada em ler texto de imagens (fotos, scans) de notas fiscais (.png, .jpg, .jpeg).
    Usa OCR para extrair todo o texto contido nela.
    Retorna uma string única com todo o texto bruto encontrado.
    """
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
    """
    Ferramenta especializada em ler texto de arquivos PDF.
    Converte cada página do PDF em uma imagem e usa OCR para extrair o texto.
    Recebe o CAMINHO para o arquivo .pdf e retorna uma string única com todo o texto.
    """
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
            if not texto_completo: return "Nenhum texto encontrado no