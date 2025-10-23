# Importa nossa nova ferramenta
from tools.extracao import extrair_texto_html
import os

# Define o caminho para o nosso arquivo de teste
caminho_arquivo = "dados_teste/nota_exemplo.html"

print(f"Iniciando teste de HTML no arquivo: {caminho_arquivo}\n")

# Verifica se o arquivo existe
if not os.path.exists(caminho_arquivo):
    print(f"--- ERRO! ---")
    print(f"Não encontrei o arquivo: {caminho_arquivo}")
    print("Verifique se você salvou o arquivo HTML na pasta 'dados_teste' com o nome correto.")
else:
    try:
        # Usamos .func() para chamar a função original
        texto_extraido = extrair_texto_html.func(caminho_arquivo)
    
        # Se funcionar, mostra o texto extraído
        print("--- SUCESSO! ---")
        print("Texto extraído do HTML (limpo):")
        print("="*30)
        print(texto_extraido)
        print("="*30)
    
    except Exception as e:
        # Se der algum erro, mostra qual foi
        print(f"\n--- ERRO! ---")
        print(f"Ocorreu um erro ao processar o arquivo HTML: {e}")