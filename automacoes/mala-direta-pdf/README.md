# Mala direta com PDF personalizado

Lê uma planilha em que cada linha é uma pessoa, preenche os campos variáveis de um PDF
modelo, gera um arquivo por linha e envia cada PDF por e-mail para o endereço da própria
linha. Planilha com 30 linhas, 30 PDFs, 30 e-mails.

```
planilha.xlsx ──► PDF personalizado ──► e-mail com o anexo
   (1 linha)         (1 arquivo)            (1 destinatário)
```

O modelo continua sendo o seu PDF fechado (o que veio do design). Os valores são
desenhados por cima, em coordenadas que você define uma vez, sem mexer no layout.

## Instalação

Requer Python 3.11 ou superior.

```bash
cd automacoes/mala-direta-pdf
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Teste a instalação rodando o exemplo completo que acompanha o projeto:

```bash
mala-direta --config exemplos/config.toml conferir
```

## Configuração em 4 passos

### 1. Credenciais de envio

Copie `.env.exemplo` para `.env` e preencha. Esse arquivo nunca vai para o Git.

```bash
cp .env.exemplo .env
```

Para Gmail ou Google Workspace: ative a verificação em duas etapas na conta e gere uma
senha de app em https://myaccount.google.com/apppasswords. A senha de app tem 16
caracteres e substitui a senha normal no `.env`. A senha da sua conta não funciona no SMTP.

### 2. Planilha

Aceita `.xlsx`, `.xlsm`, `.csv` e `.tsv`. A primeira linha são os títulos das colunas, e
uma delas tem o e-mail. Os títulos são comparados ignorando maiúsculas, acentos e
pontuação, então `E-mail`, `email` e `E-Mail` são a mesma coluna.

```csv
nome,email,curso,carga horaria,data
Ana Beatriz Ribeiro,ana@exemplo.com,Claude for Business,16,12/09/2026
```

### 3. Coordenadas dos campos no PDF

Gere uma cópia do seu modelo com uma régua por cima e leia os valores de `x` e `y`:

```bash
mala-direta grade
```

Abra o PDF gerado em `saida/pdfs/modelo-com-grade.pdf`. As linhas vermelhas são o eixo x
(da esquerda para a direita) e as azuis o eixo y, contado **de baixo para cima**, que é o
padrão do formato PDF. Os números estão em pontos (1 pt = 1/72 de polegada; uma página A4
tem 595 x 842 pt).

### 4. config.toml

Todo o resto é declarado em um arquivo TOML. O exemplo comentado está em
`exemplos/config.toml`; copie e ajuste:

```toml
[planilha]
arquivo = "participantes.xlsx"
coluna_email = "email"
# aba = "Turma 1"            # opcional; sem isso usa a primeira aba

[pdf]
modelo = "certificado.pdf"
diretorio_saida = "saida/pdfs"
nome_arquivo = "certificado-{nome}.pdf"

[[pdf.campos]]
texto = "{Nome} {Sobrenome}"   # molde: combina colunas e texto fixo
x = 421
y = 330
fonte = "Helvetica-Bold"
tamanho = 28
cor = "#12263f"
alinhamento = "centro"        # esquerda, centro ou direita
largura_maxima = 620          # opcional: diminui a fonte até o nome caber

[[pdf.campos]]
texto = "carga horária de {carga horaria} horas"
x = 421
y = 232

[valores]
# Valores iguais para toda a turma, que não precisam estar na planilha.
# A planilha tem precedência: se a coluna existir lá, o valor da linha vence.
data = "09/10/2026"
"carga horaria" = "16"

[mensagem]
assunto = "Seu certificado do treinamento {curso}"
corpo_texto = "corpo.txt"
corpo_html = "corpo.html"                  # opcional
remetente_nome = "AYA Academy"
responder_para = "contato@aya.tec.br"      # opcional
nome_anexo = "Certificado - {nome}.pdf"    # opcional

[envio]
pausa_segundos = 2.0
registro = "saida/registro.csv"
```

No assunto, no corpo, nos campos do PDF e nos nomes de arquivo, `{coluna}` é trocado pelo
valor daquela linha. Os títulos são tolerantes: `{Nome}`, `{nome}` e `{NOME}` encontram a
mesma coluna.

### Preencher espaços separados (dia, mês e ano)

Quando o modelo já tem as barras impressas e só deixa os espaços em branco, um campo pode
desenhar apenas um pedaço do valor:

```toml
[[pdf.campos]]
texto = "{data}"
dividir_por = "/"
pedaco = 1        # 1 = dia, 2 = mês, 3 = ano em 09/10/2026
x = 1721
y = 387.5
```

Três blocos como esse preenchem a data inteira, cada um na sua posição.

## Uso

Sempre na mesma ordem, do mais seguro para o definitivo:

```bash
mala-direta conferir                  # valida tudo e gera uma amostra da 1ª linha
mala-direta gerar                     # gera os 30 PDFs, sem enviar nada
mala-direta enviar                    # SIMULA o envio (monta as mensagens e para aí)
mala-direta enviar --limite 1         # envia de verdade? não: ainda é simulação
mala-direta enviar --confirmar        # agora sim, envia
```

O comando `enviar` só entrega mensagens com `--confirmar`. Sem essa opção ele faz todo o
trabalho e mostra o que aconteceria, o que é a forma barata de descobrir um erro antes de
mandar para a lista inteira.

Antes do disparo geral, mande um teste real para você mesma:

```bash
mala-direta enviar --somente veronica@aya.tec.br --confirmar
```

Opções úteis em qualquer comando de lote:

| Opção | Para que serve |
| --- | --- |
| `--limite N` | processa só as N primeiras linhas |
| `--somente EMAIL` | restringe a um endereço (pode repetir a opção) |
| `--reenviar` | ignora o registro e manda de novo para quem já recebeu |
| `--config caminho` | usa outro arquivo de configuração |
| `--valor COLUNA=VALOR` | define um valor igual para todas as linhas (repetível) |

## Reexecução é segura

Cada linha processada vira uma linha em `saida/registro.csv` com data, e-mail, arquivo,
status e o detalhe do erro quando houve. Quem já consta como `enviado` é pulado
automaticamente na próxima execução.

Na prática: se a internet cair no meio de um lote de 30, rode o mesmo comando de novo.
Os 12 que já receberam são pulados e os 18 restantes seguem. Uma falha em uma linha
(caixa cheia, endereço inexistente) não derruba o lote: ela é registrada como `erro`,
as outras continuam, e a reexecução tenta só as pendentes.

## Limites e cuidados de entrega

- **Cota do Google**: cerca de 500 destinatários por dia em contas gratuitas e 2.000 em
  contas Workspace. Lotes maiores precisam ser divididos por dia ou migrados para um
  serviço transacional.
- **Tamanho**: 25 MB por mensagem no Gmail, anexo incluído.
- **Ritmo**: `pausa_segundos` dá um respiro entre as mensagens. Dois segundos é um valor
  conservador e suficiente para lotes de dezenas.
- **Conteúdo**: e-mail com anexo e texto curto tende a cair em spam com mais facilidade.
  Escreva um corpo de verdade, com contexto, e evite links encurtados.

## Trocar o canal de envio

O pipeline depende do protocolo `EnviadorEmail` (em `envio.py`), não do `smtplib`. Migrar
para a API do Gmail, Resend ou SendGrid é escrever uma classe nova com os métodos
`remetente`, `enviar` e `fechar` e passá-la para `executar()`. Nada mais muda.

Vale a migração quando o admin do Workspace bloquear senhas de app, quando o volume
passar da cota diária, ou quando a automação for rodar sem supervisão em um servidor.

## Desenvolvimento

```bash
pytest          # 70 testes, roda em menos de 1 segundo
ruff check .
ruff format .
```

Os testes não tocam a rede: o envio é substituído por um `EnviadorSimulado` que guarda as
mensagens em memória, e o SMTP real é testado com conexão simulada.

## Estrutura

```
src/mala_direta/
  config.py      configuração TOML validada + credenciais do ambiente
  planilha.py    leitura e validação das linhas (.xlsx, .csv)
  texto.py       substituição de {placeholders} e nomes de arquivo seguros
  pdf.py         desenho dos valores sobre o modelo e a régua de coordenadas
  envio.py       montagem da mensagem e entrega (protocolo + implementação SMTP)
  pipeline.py    orquestração do lote e registro de envios
  cli.py         interface de linha de comando
exemplos/        projeto completo funcionando, com modelo e planilha de exemplo
certificado-incompany/   configuração real do certificado do Claude InCompany
tests/           suíte de testes
```

Regra de dependência: `cli` chama `pipeline`, que compõe `planilha`, `pdf`, `texto` e
`envio`. Nenhum desses quatro conhece os outros três nem a linha de comando.

## Certificado do Claude InCompany

A pasta `certificado-incompany/` já vem configurada para o certificado de participação,
com as coordenadas extraídas do próprio PDF modelo (página de 3020 x 2150 pt): nome
centralizado em y = 1266, data repartida nos três espaços entre as barras impressas, e
carga horária à esquerda do rótulo "HORAS".

A planilha esperada é a exportação do formulário pré-treinamento, com as colunas `Nome`,
`Sobrenome` e `E-mail`. Data e carga horária mudam por turma e entram na linha de comando:

```bash
mala-direta --config certificado-incompany/config.toml \
  --valor data=09/10/2026 --valor "carga horaria=16" enviar --confirmar
```

### O PDF modelo não entra no Git

Este repositório é público e publica GitHub Pages. O certificado em branco contém a
assinatura do coordenador, então versioná-lo deixaria um certificado forjável a um
download de distância. Por isso `certificado-incompany/modelos/` está no `.gitignore`:
o PDF fica só na máquina de quem roda a automação.
