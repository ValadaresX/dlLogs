# Uma Ferramenta de Download de Logs para Análise e Monitoramento

Descrição: O dlLogs é uma aplicação projetada para tornar o processo de download e análise de logs de registro de combate do jogo World of Warcraft, ele baixa os logs de um servidor específico (confidencial). Com essa ferramenta, você pode baixar os logs de forma rápida e eficiente, além de converter o formato para JSON.

## Pré-requisitos

Certifique-se de ter instalado o Python 3.11 e as seguintes bibliotecas:

- `os`
- `re`
- `tqdm`
- `chardet`
- `pathlib`
- `urlparse`
- `requests`


## Configuração

Antes de executar o script, é necessário configurar as seguintes variáveis:

- `URL_BASE`: URL base do servidor remoto onde os logs estão armazenados, deve se criado um arquivo 'url.py' no mesmo diretório do "copy_logs.py".
- `logs_dir`: Diretório onde os logs serão salvos. O valor padrão é um subdiretório chamado "logs" no diretório de trabalho.

## Futuras implementações

- [x] Finalização do aquivo de download.
- [x] Implementação de barra de progresso do download.
- [x] Finalização das docstring do arquivo de download.
- [x] Finalização para os testes unitários do script de download.
- [x] Refatorar o código.
- [ ] Finalização do aquivo de conversão de logs.
- [ ] Finalização da interface gráfica. 



## Uso

Para executar o script, basta executar o arquivo Python `copy_logs.py`. Os logs serão baixados para o diretório especificado em `logs_dir`.

Durante a execução, o script verifica se todos os logs estão presentes no disco. Se algum log estiver faltando, ele será baixado. Caso contrário, uma mensagem informando que todos os logs estão presentes será exibida.

O script também é executado em intervalos regulares entre 8 e 10 horas. Durante esse intervalo, uma contagem regressiva será exibida. Após o término da contagem, o script verificará e baixará novos logs, se disponíveis.

## Observações

- O script assume que a codificação dos arquivos de log é UTF-8. Caso contrário, ele tentará detectar a codificação correta usando a biblioteca `chardet`.
- O tamanho máximo de cada arquivo de log a ser lido é definido por `chunk_size`. Arquivos maiores serão lidos parcialmente.
- O progresso do download é exibido usando a biblioteca `tqdm`.

