# Importa a nossa função .func do arquivo de ferramentas
from tools.extracao import extrair_dados_xml
import os

# Define o caminho para o nosso arquivo de teste
caminho_arquivo = "dados_teste/nota_fiscal_exemplo.xml"

print(f"Iniciando teste de XML no arquivo: {caminho_arquivo}\n")

# Verifica se o arquivo existe
if not os.path.exists(caminho_arquivo):
    print(f"--- ERRO! ---")
    print(f"Não encontrei o arquivo: {caminho_arquivo}")
else:
    try:
        # --- AQUI ESTÁ A MUDANÇA ---
        # Usamos .func() para chamar a função original "dentro" do @tool
        dados_extraidos_string = extrair_dados_xml.func(caminho_arquivo)

        # Se funcionar, mostra os dados na tela (agora como string)
        print("\n--- SUCESSO! ---")
        print("Dados extraídos da Nota Fiscal (como string):")
        print("="*30)
        print(dados_extraidos_string)
        print("="*30)

    except Exception as e:
        # Se der algum erro, mostra qual foi
        print(f"\n--- ERRO! ---")
        print(f"Ocorreu um erro ao processar o arquivo: {e}")