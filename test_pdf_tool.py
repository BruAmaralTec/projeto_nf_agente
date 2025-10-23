# Importa nossa nova ferramenta
from tools.extracao import extrair_texto_pdf
import os

# Define o caminho para o nosso arquivo de teste
caminho_arquivo = "dados_teste/nota_exemplo.pdf"

print(f"Iniciando teste de PDF no arquivo: {caminho_arquivo}\n")

# Verifica se o arquivo existe
if not os.path.exists(caminho_arquivo):
    print(f"--- ERRO! ---")
    print(f"Não encontrei o arquivo: {caminho_arquivo}")
    print("Verifique se você salvou o arquivo PDF na pasta 'dados_teste' com o nome correto.")
else:
    try:
        # Usamos .func() para chamar a função original
        texto_extraido = extrair_texto_pdf.func(caminho_arquivo)
    
        # Se funcionar, mostra o texto extraído
        print("--- SUCESSO! ---")
        print("Texto extraído do PDF (via OCR):")
        print("="*30)
        print(texto_extraido)
        print("="*30)
    
    except Exception as e:
        # Se der algum erro, mostra qual foi
        print(f"\n--- ERRO! ---")
        print(f"Ocorreu um erro ao processar o arquivo PDF: {e}")
        print("\nPossíveis causas:")
        print("1. A biblioteca 'pdf2image' não foi instalada.")
        print("2. O 'Poppler' não foi instalado ou não está no PATH do sistema.")
        print("3. Você não reiniciou o VSCode depois de instalar o Poppler.")