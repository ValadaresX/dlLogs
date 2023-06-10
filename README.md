# Script de Download de Logs

Este script em Python realiza o download de logs de um servidor remoto. Ele busca um arquivo XML no servidor que contém informações sobre os logs disponíveis. Em seguida, verifica quais logs estão ausentes no diretório local e faz o download apenas dos logs que ainda não foram baixados.

## Pré-requisitos

Certifique-se de ter instalado o Python 3.11 e as seguintes bibliotecas:

- `requests`
- `tqdm`
- `chardet`

## Configuração

Antes de executar o script, é necessário configurar as seguintes variáveis:

- `URL_BASE`: URL base do servidor remoto onde os logs estão armazenados.
- `BASE_DIR`: Diretório base onde os logs serão salvos. O valor padrão é o diretório de trabalho atual.
- `KEYS_FILE`: Caminho para o arquivo `keys.txt`, que armazenará as chaves dos logs baixados.
- `LOGS_DIR`: Diretório onde os logs serão salvos. O valor padrão é um subdiretório chamado "logs" no diretório de trabalho.

## Uso

Para executar o script, basta executar o arquivo Python `copy_logs.py`. Os logs serão baixados para o diretório especificado em `LOGS_DIR`.

Durante a execução, o script verifica se todos os logs estão presentes no disco. Se algum log estiver faltando, ele será baixado. Caso contrário, uma mensagem informando que todos os logs estão presentes será exibida.

O script também é executado em intervalos regulares entre 8 e 10 horas. Durante esse intervalo, uma contagem regressiva será exibida. Após o término da contagem, o script verificará e baixará novos logs, se disponíveis.

## Observações

- O script assume que a codificação dos arquivos de log é UTF-8. Caso contrário, ele tentará detectar a codificação correta usando a biblioteca `chardet`.
- O tamanho máximo de cada arquivo de log a ser lido é definido por `MAX_BYTES`. Arquivos maiores serão lidos parcialmente.
- O progresso do download é exibido usando a biblioteca `tqdm`.

