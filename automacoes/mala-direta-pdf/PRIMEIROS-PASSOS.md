# Primeiros passos no Mac

Guia para quem nunca rodou um projeto em Python. Do zero ao primeiro certificado
enviado, em cerca de 20 minutos. Você vai digitar comandos no Terminal: ele é um
programa do próprio Mac, abra com `Cmd + Espaço`, digite "Terminal" e tecle Enter.

Copie e cole um comando por vez, apertando Enter depois de cada um.

## 1. Confira a versão do Python

```bash
python3 --version
```

Se aparecer **3.11 ou maior**, siga para o passo 2.

Se aparecer menos que isso (o Mac costuma vir com 3.9), baixe o instalador em
https://www.python.org/downloads/macos/, abra o arquivo `.pkg` e siga adiante
clicando em continuar. Depois feche o Terminal, abra de novo e repita o comando.

A versão que vem de fábrica no Mac é antiga e existe para uso interno do sistema.
Instalar outra ao lado dela não quebra nada: as duas convivem.

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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[web]"
```

O primeiro comando cria uma caixa isolada para as dependências, sem bagunçar o
resto do Mac. O segundo entra nela: quando estiver ativa, o Terminal mostra
`(.venv)` no começo da linha. **Toda vez que abrir o Terminal de novo, repita o
`source .venv/bin/activate`.**

## 4. Coloque o PDF do certificado

Salve o `Certificado_InCompany_Empty.pdf` na pasta `certificado-incompany/modelos/`.
Pelo Finder é mais fácil: abra a pasta do projeto com

```bash
open certificado-incompany/modelos
```

e arraste o arquivo para a janela que abrir.

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
mala-direta --config certificado-incompany/config.toml conferir
```

Ele valida tudo e gera uma amostra. Abra para conferir as posições:

```bash
open certificado-incompany/saida/pdfs
```

## 7. Mande um teste para você mesma

```bash
mala-direta --config certificado-incompany/config.toml \
  --somente veronica@ayatech.co enviar --confirmar
```

No e-mail recebido, confira: o remetente aparece como `no-reply@ayatech.co`, o
anexo abre, e o nome está centralizado.

## 8. Envie para a turma

Troque o arquivo `certificado-incompany/participantes.csv` pela exportação do
formulário e rode:

```bash
mala-direta --config certificado-incompany/config.toml enviar
```

Repare: **sem `--confirmar` ele apenas simula**, mostrando o que aconteceria. Só
depois de conferir a simulação, repita o comando com `--confirmar` no final.

Se a internet cair no meio, rode o mesmo comando de novo: quem já recebeu é
pulado automaticamente.

## A interface no navegador

Para não depender de comandos no dia a dia:

```bash
mala-direta hash-senha          # crie sua senha de acesso e cole no .env
mala-direta-web
```

Depois abra http://127.0.0.1:8000 no navegador. Enquanto o Terminal estiver
aberto com esse comando rodando, a interface fica no ar na sua máquina. Para
desligar, tecle `Ctrl + C` no Terminal.

## Quando algo der errado

Os erros são escritos para serem lidos. Alguns comuns:

| O que aparece | O que fazer |
| --- | --- |
| `command not found: mala-direta` | Rode `source .venv/bin/activate` |
| `PDF modelo não encontrado` | Falta o passo 4 |
| `Variáveis de ambiente ausentes` | Falta preencher o `.env` do passo 5 |
| `Preencha antes de continuar` | Algum valor da turma ainda está com o texto de exemplo |
| `Servidor recusou as credenciais` | A senha de app está errada ou foi gerada em outra conta |
| `Directory cannot be installed in editable mode` | O pip está velho: rode `python -m pip install --upgrade pip` e repita a instalação |
| `requires-python` ou `Package requires a different Python` | A caixa `.venv` foi criada com um Python antigo. Apague com `rm -rf .venv` e refaça o passo 3 usando `python3.12 -m venv .venv` |
