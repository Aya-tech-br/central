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

Copie `.env.exemplo` para `.env` e preencha. Esse arquivo nunca vai para o Git, e cada
variável tem um comentário explicando o que ela é.

```bash
cp .env.exemplo .env
```

Existem dois canais de envio, escolhidos pela variável `EMAIL_CANAL`:

| | **API (Resend)** | **SMTP (Gmail/Workspace)** |
| --- | --- | --- |
| Credencial | uma chave de API | senha de app de 16 caracteres |
| Remetente em domínio próprio | verificação por DNS no painel | exige alias + "Enviar e-mail como" |
| Limite diário | pelo plano contratado | ~500 (grátis) ou ~2.000 (Workspace) |
| Erros | resposta da API dizendo o motivo | código SMTP, às vezes silencioso |

Prefira a **API quando o endereço do remetente for de um domínio diferente da conta que
autentica** (um `no-reply@` em domínio próprio, por exemplo). Nesse caso o SMTP do Google
costuma reescrever o remetente sem avisar, e a mensagem chega assinada por outra pessoa.
Prefira **SMTP quando o envio sai da própria conta de trabalho** e o volume é pequeno:
não precisa contratar nada.

Trocar de canal depois é mudar uma linha do `.env`. Nenhum outro arquivo muda.

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
pytest          # 95 testes, roda em menos de 1 segundo
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
  envio.py       montagem da mensagem e o protocolo de entrega
  canais.py      implementações de entrega (SMTP e API) e a escolha entre elas
  pipeline.py    orquestração do lote e registro de envios
  cli.py         interface de linha de comando
  web/           interface web (app FastAPI, login e catálogo de modelos)
exemplos/        projeto completo funcionando, com modelo e planilha de exemplo
certificado-incompany/   configuração real do certificado do Claude InCompany
tests/           suíte de testes
```

Regra de dependência: `cli` chama `pipeline`, que compõe `planilha`, `pdf`, `texto` e
`envio`. Nenhum desses quatro conhece os outros três nem a linha de comando.

## Interface web

Para quem vai disparar os certificados sem mexer em arquivo de configuração: escolher o
modelo, preencher os dados da turma, conferir uma amostra e enviar, tudo pelo navegador.

```bash
pip install -e ".[web]"
mala-direta-web                      # abre em http://127.0.0.1:8000
```

### Login sem banco de dados

As senhas ficam em hash bcrypt numa variável de ambiente e a sessão vive num cookie
assinado. Nada é gravado em banco.

```bash
mala-direta hash-senha               # digite a senha; ele imprime "usuario:$2b$12$..."
python -c "import secrets; print(secrets.token_urlsafe(48))"   # chave da assinatura
```

No `.env`, junto das variáveis SMTP:

```bash
MALA_DIRETA_USUARIOS=veronica:$2b$12$...,breno:$2b$12$...
MALA_DIRETA_CHAVE_SECRETA=<a chave gerada acima>
```

O cookie é `HttpOnly`, `SameSite=Lax` e ganha a marca `Secure` quando a conexão é HTTPS.
O login tem rate limit de 5 tentativas a cada 15 minutos por origem, e usuário inexistente
recebe exatamente a mesma resposta de senha errada, para não revelar quem existe.

### Como funciona

1. Escolha o modelo de certificado. A lista vem das pastas que têm um `config.toml`.
2. Preencha os dados da turma (data, carga horária). Os campos aparecem sozinhos, a partir
   do `[valores]` daquele modelo.
3. Envie a planilha exportada do formulário.
4. Clique em **Ver amostra do PDF**: o certificado da primeira linha abre numa aba nova.
5. Marque a confirmação (o botão de envio só habilita depois dela) e envie. A tela mostra o
   andamento linha a linha, e o histórico fica disponível para download em CSV.

### Adicionar o Claude For Business

Crie a pasta `certificado-forbusiness/` com o seu `config.toml` (copie o do InCompany e
ajuste as coordenadas) e o modelo aparece na interface. Nenhuma linha de código muda.

### Se for hospedar

A interface roda em um processo só, porque o andamento dos envios fica em memória. Para
colocar no ar:

- **HTTPS obrigatório**, senão o cookie de sessão viaja sem a marca `Secure`.
- **Um worker apenas** (`mala-direta-web` já sobe assim).
- **Disco persistente** para `saida/`: é lá que fica o `registro.csv` que impede envio
  duplicado. Em plataformas com disco efêmero, monte um volume ou baixe o registro ao fim
  de cada turma.
- **Segredos por variável de ambiente**, nunca no repositório.

### Enviar de um endereço no-reply

Para o e-mail sair de `no-reply@aya.tec.br` sem gastar uma licença nova, cadastre o
endereço como **alias** da conta que autentica (Admin Console → Usuários → Aliases de
e-mail) e, na conta dela, em Gmail → Configurações → Contas e importação → "Enviar e-mail
como". Sem esse segundo passo o Google reescreve silenciosamente o remetente de volta
para a conta autenticada.

```bash
SMTP_USUARIO=conta-real@aya.tec.br     # quem autentica
SMTP_REMETENTE=no-reply@aya.tec.br     # quem aparece como remetente
```

Um alias continua **recebendo** mensagens: respostas caem na caixa da conta principal em
vez de voltar como erro. Por isso o texto do e-mail aponta um canal de contato de
verdade em vez de prometer resposta ali.

#### Configurar o provedor de API, passo a passo

1. **Crie a conta** em https://resend.com e confirme o e-mail. O plano gratuito atende
   lotes de dezenas de certificados; confira os limites atuais no painel.
2. **Adicione o domínio** em Domains → Add Domain, informando `ayatech.co`. Escolha a
   região de envio mais próxima (a da América do Norte é a padrão).
3. **Publique os registros de DNS** que a tela mostrar, no painel de quem hospeda o DNS
   do domínio. São em geral três, e cada um tem uma função:
   - um **MX** num subdomínio de envio, por onde voltam as rejeições;
   - um **TXT de SPF**, que autoriza o provedor a enviar em nome do domínio;
   - um **TXT de DKIM**, a chave que assina cada mensagem.
   Copie e cole exatamente como o painel mostra, sem reescrever. Se o seu provedor de DNS
   já acrescenta o domínio ao final do nome, não repita o `ayatech.co`.
4. **Espere a verificação.** Costuma levar minutos, mas o DNS pode demorar algumas horas.
   O painel marca o domínio como verificado sozinho.
5. **Gere a chave** em API Keys → Create API Key, com permissão apenas de envio
   (*Sending access*). Ela aparece **uma única vez**: copie na hora. Se perder, apague a
   chave e gere outra.
6. **Preencha o `.env`** com a chave e o remetente, e nada mais:

   ```bash
   EMAIL_CANAL=resend
   RESEND_API_KEY=re_...
   EMAIL_REMETENTE=AYA Academy <no-reply@ayatech.co>
   ```

7. **Teste com você mesma** antes da turma inteira:

   ```bash
   mala-direta --config certificado-incompany/config.toml \
     --somente seu.email@aya.tec.br enviar --confirmar
   ```

   Confira no e-mail recebido: o remetente aparece como `no-reply@ayatech.co`, o anexo
   abre, e o nome está no lugar certo do certificado.

Se o domínio ainda não estiver verificado, o envio falha com uma mensagem dizendo isso,
em vez de sair errado. Se a conta já usa SendGrid, Mailgun ou Brevo, o canal equivalente
são 40 linhas: a classe nova implementa o mesmo protocolo e o resto do sistema não muda.

### Valores que precisam ser preenchidos

Qualquer entrada de `[valores]` cujo texto ainda comece com `PREENCHER` interrompe o lote
antes do primeiro envio. É a rede de proteção contra mandar trinta certificados com um
texto de exemplo no corpo do e-mail.

## Certificado do Claude InCompany

A pasta `certificado-incompany/` já vem configurada para o certificado de participação,
com as coordenadas extraídas do próprio PDF modelo (página de 3020 x 2150 pt): nome
centralizado em y = 1266, data repartida nos três espaços entre as barras impressas, e
carga horária à esquerda do rótulo "HORAS".

O nome é escrito em **Instrument Sans Bold**, escolhida por comparação direta com o texto
fixo do próprio certificado: entre as fontes livres testadas, é a que mais se aproxima no
desenho do "C", do "a" e no espaçamento. O arquivo e a licença OFL ficam em
`certificado-incompany/fontes/`, então não há nada a instalar. Para usar a fonte original
da identidade, troque o `.ttf` da pasta e o nome em `[[pdf.fontes]]`.

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
