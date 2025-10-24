# Guia Completo do Agente Extrator de NF - Meta Singularity

## 1. Visão Geral
*Este sistema utiliza IA para extrair dados de notas fiscais.*

## 2. Usando a Interface Web (Streamlit)
*Explicação sobre como usar a tela inicial, os modos e o chat.*
- **Modo Arquivo Único:** Gera um Excel por nota.
- **Modo Compilado:** Gera um Excel com todas as notas.
  - **Upload Individual:** Um arquivo por vez.
  - **Múltiplos Arquivos:** Vários arquivos de uma vez.

## 3. Formatos Suportados
*PDF, XML, HTML, PNG, JPG, JPEG.*
*Dicas para OCR...*

## 4. Arquivos de Saída (Excel)
*Explicação sobre os nomes dos arquivos e as colunas.*

## 5. Usando a API (Para Desenvolvedores)
*Endpoint: POST /processar_nf/*
*Parâmetros: file, app_mode*
*Resposta: JSON com os dados extraídos.*
*Exemplo Python...*

## 6. Solução de Problemas
*O que fazer se...?*