# Primeiros passos no Mac

Do zero ao primeiro certificado enviado. Você vai digitar alguns comandos no
Terminal: ele é um programa do próprio Mac. Abra com `Cmd + Espaço`, digite
"Terminal" e tecle Enter. Copie e cole um comando por vez, apertando Enter
depois de cada um.

Você **não precisa instalar Python**. A ferramenta abaixo cuida disso.

## 1. Instale o uv (uma vez só)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ele instala e gerencia as versões de Python sozinho, sem mexer na que vem com o
Mac. Quando terminar, **feche o Terminal e abra de novo**.

## 2. Baixe o projeto

```bash
cd ~/Documents
git clone -b claude/happy-galileo-wflp4x https://github.com/Aya-tech-br/central.git
cd central/automacoes/mala-direta-pdf
```

Na primeira vez o Mac pode abrir uma janela pedindo para instalar as "ferramentas
de linha de comando". Aceite, espere terminar e rode o `git clone` de novo.

A partir daqui, **todos os comandos são dados nesta pasta**. Se fechar o Terminal
e voltar depois, entre nela de novo com:

```bash
cd ~/Documents/central/automacoes/mala-direta-pdf
```

## 3. Instale o programa

```bash
uv sync
```

Esse comando baixa a versão certa do Python e todas as dependências, numa pasta
isolada dentro do projeto. Pode demorar um ou dois minutos na primeira vez.

Daqui em diante, todo comando começa com `uv run`. Não existe nada para "ativar"
ao reabrir o Terminal.

## 4. Coloque o PDF do certificado

Cada modelo tem a sua pasta. Para o InCompany:

```bash
open certificado-incompany/modelos
```

Arraste o `Certificado_InCompany_Empty.pdf` para a janela que abrir. Para o
Claude for Business, o mesmo em `certificado-forbusiness/modelos`.

## 5. Preencha as credenciais

```bash
cp .env.exemplo .env
open -e .env
```

O segundo comando abre o arquivo no TextEdit. Troque a linha da senha pelas 16
letras da senha de app do Google, salve com `Cmd + S` e feche.

Esse arquivo guarda segredos e nunca é enviado ao GitHub.

## 6. Confira antes de enviar

```bash
uv run mala-direta --config certificado-incompany/config.toml conferir
```

Ele valida tudo e gera uma amostra. Abra para conferir as posições:

```bash
open certificado-incompany/saida/pdfs
```

## 7. Mande um teste para você mesma

```bash
uv run mala-direta --config certificado-incompany/config.toml \
  --somente veronica@ayatech.co enviar --confirmar
```

No e-mail recebido, confira: o remetente aparece como `no-reply@ayatech.co`, o
anexo abre, e o nome está centralizado.

## 8. Envie para a turma

Troque o `certificado-incompany/participantes.csv` pela exportação do formulário
e rode:

```bash
uv run mala-direta --config certificado-incompany/config.toml enviar
```

Repare: **sem `--confirmar` ele apenas simula**, mostrando o que aconteceria. Só
depois de conferir a simulação, repita o comando com `--confirmar` no final.

Se a internet cair no meio, rode o mesmo comando de novo: quem já recebeu é
pulado automaticamente.

## A interface no navegador

Para não depender de comandos no dia a dia:

```bash
uv run mala-direta hash-senha      # crie sua senha de acesso e cole no .env
uv run mala-direta-web
```

Depois abra http://127.0.0.1:8000 no navegador. Enquanto o Terminal estiver
aberto com esse comando rodando, a interface fica no ar na sua máquina. Para
desligar, tecle `Ctrl + C` no Terminal.

Na interface você escolhe o modelo (InCompany ou For Business), preenche os
dados da turma, envia a planilha, confere a amostra e dispara, sem digitar
comando nenhum.

## Quando algo der errado

Os erros são escritos para serem lidos. Alguns comuns:

| O que aparece | O que fazer |
| --- | --- |
| `command not found: uv` | Feche e abra o Terminal de novo, depois do passo 1 |
| `PDF modelo não encontrado` | Falta o passo 4 |
| `Variáveis de ambiente ausentes` | Falta preencher o `.env` do passo 5 |
| `Preencha antes de continuar` | Algum valor da turma ainda está com o texto de exemplo |
| `Servidor recusou as credenciais` | A senha de app está errada ou foi gerada em outra conta |
| `Colunas ausentes na planilha` | A exportação não tem as colunas Nome, Sobrenome e E-mail |

## Se você já tem Python 3.11 ou mais novo

O caminho tradicional também funciona, sem o uv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
mala-direta --help
```

Nesse caso, lembre de rodar `source .venv/bin/activate` toda vez que abrir o
Terminal, e de omitir o `uv run` dos comandos deste guia.
