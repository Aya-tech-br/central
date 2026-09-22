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
coluna = "nome"
x = 421
y = 330
fonte = "Helvetica-Bold"
tamanho = 28
cor = "#12263f"
alinhamento = "centro"        # esquerda, centro ou direita
largura_maxima = 620          # opcional: diminui a fonte até o nome caber

[[pdf.campos]]
coluna = "carga horaria"
formato = "carga horária de {valor} horas"   # opcional: texto fixo ao redor do valor
x = 421
y = 232

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

No assunto, no corpo e nos nomes de arquivo, `{coluna}` é trocado pelo valor daquela
linha. Vale qualquer coluna da planilha, não só as que entram no PDF.

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
pytest          # 59 testes, roda em menos de 1 segundo
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
tests/           suíte de testes
```

Regra de dependência: `cli` chama `pipeline`, que compõe `planilha`, `pdf`, `texto` e
`envio`. Nenhum desses quatro conhece os outros três nem a linha de comando.
