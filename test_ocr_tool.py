# Importa nossa nova ferramenta .func
from tools.extracao import extrair_texto_imagem
import os

# Define o caminho para o nosso arquivo de teste
caminho_arquivo = "dados_teste/imagem_exemplo.png"

print(f"Iniciando teste de OCR no arquivo: {caminho_arquivo}\n")

# Verifica se o arquivo existe antes de tentar
if not os.path.exists(caminho_arquivo):
    print(f"--- ERRO! ---")
    print(f"Não encontrei o arquivo: {caminho_arquivo}")
    print("Verifique se o nome e o local estão corretos.")
else:
    try:
        # --- AQUI ESTÁ A MUDANÇA ---
        # Usamos .func() para chamar a função original "dentro" do @tool
        texto_extraido = extrair_texto_imagem.func(caminho_arquivo)
    
        # Se funcionar, mostra o texto extraído
        print("--- SUCESSO! ---")
        print("Texto extraído da imagem:")
        print("="*30)
        print(texto_extraido)
        print("="*30)
    
    except Exception as e:
        # Se der algum erro, mostra qual foi
        print(f"\n--- ERRO! ---")
        print(f"Ocorreu um erro ao processar a imagem: {e}")
        print("\nPossíveis causas:")
        print("1. O Tesseract não foi instalado corretamente.")
        print("2. A biblioteca 'opencv-python' ou 'pytesseract' não foi instalada.")
        print("3. O idioma 'por' (Português) do Tesseract não foi instalado.")