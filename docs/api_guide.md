# Guia da API Meta Singularity NF Extract v1.0

Bem-vindo ao guia da API para o Agente Extrator de Notas Fiscais da Meta Singularity. Esta API permite processar arquivos de notas fiscais (PDF, XML, Imagens, HTML) e receber os dados extraídos em formato JSON.

## URL Base

A API está hospedada no Render e a URL base é:

`https://meta-singularity-api-nf-agente.onrender.com` 

*(Esta é a sua URL pública no Render)*

## Endpoint Principal

Existe um único endpoint principal para o processamento:

* **Endpoint:** `/processar_nf/`
* **Método HTTP:** `POST`

## Autenticação

Atualmente (v1.0), a API não requer autenticação.

## Corpo da Requisição (Input)

A requisição deve ser enviada como `multipart/form-data` e conter dois campos:

1.  **`file`**:
    * **Tipo:** Arquivo
    * **Descrição:** O arquivo da nota fiscal a ser processado.
    * **Formatos Suportados:** `.pdf`, `.xml`, `.html`, `.png`, `.jpg`, `.jpeg`

2.  **`mode`**:
    * **Tipo:** String (texto)
    * **Descrição:** Define o modo de operação do agente.
    * **Valores Possíveis:**
        * `single`: Processa o arquivo e salva os dados em um novo arquivo Excel com nome único (ex: `NotaFiscal_XXX.xlsx`). Retorna os dados extraídos deste arquivo.
        * `accumulated`: Processa o arquivo e adiciona os dados extraídos ao final de um arquivo Excel mestre (`COMPILADO_MESTRE.xlsx`). Retorna os dados extraídos *deste último arquivo processado*.

## Resposta da API (Output)

### Sucesso (Código HTTP 200)

Se o processamento for bem-sucedido, a API retornará um JSON contendo os dados extraídos da nota fiscal. Os campos presentes no JSON dependerão do que o agente conseguiu encontrar no arquivo. Todos os campos são opcionais.

**Exemplo de Resposta JSON:**

```json
{
  "chave_acesso": "41250879379491013838650060001212091902485866",
  "numero_nf": "121209",
  "data_emissao": "24/08/2025 11:08:58",
  "cnpj_emitente": "79.379.491/0138-38",
  "nome_emitente": "HAVAN S.A.",
  "endereco_emitente": "AV NOSSA SENHORA APARECIDA, 155, SANTA TEREZINHA",
  "municipio_emitente": "FAZENDA RIO GRANDE, PR",
  "cnpj_cpf_destinatario": "005.589.799-12",
  "nome_destinatario": "Bruna Do Amaral",
  "endereco_destinatario": null,
  "municipio_destinatario": null,
  "valor_total": 459.88,
  "base_calculo": null,
  "valor_iss": null,
  "valor_icms": null,
  "discriminacao_servicos": null
}