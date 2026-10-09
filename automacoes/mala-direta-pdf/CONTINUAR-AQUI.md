# Continuar daqui

Documento de passagem: o que já foi feito, o que falta e as armadilhas que já
apareceram. Escrito para quem abrir uma sessão nova (humana ou com o Claude
Code) direto na máquina.

## O que é este projeto

Automação de mala direta com PDF personalizado. Lê uma planilha em que cada
linha é uma pessoa, escreve os dados variáveis sobre um PDF modelo fechado, gera
um arquivo por participante e envia por e-mail com o certificado em anexo.

Tem duas interfaces: linha de comando e uma web com login, que faz a mesma coisa
pelo navegador.

## Onde está

| | |
| --- | --- |
| Repositório | `Aya-tech-br/central` (público) |
| Branch | `claude/happy-galileo-wflp4x` |
| Pasta no repositório | `automacoes/mala-direta-pdf/` |
| Pasta no Mac da Verônica | `~/Documents/central/automacoes/mala-direta-pdf` |
| Pull request | ainda não aberto |

## Estado atual

Funcionando e verificado:

- Geração dos certificados **Claude InCompany** e **Claude for Business**, com
  nome, data e carga horária nas posições certas, acentos e cedilha corretos, e
  redução automática da fonte em nomes longos.
- Envio por SMTP ou por API, montagem da mensagem com anexo, registro em CSV que
  impede envio duplicado, simulação como padrão.
- Interface web com login, escolha do modelo, dados da turma, amostra do PDF e
  acompanhamento do envio.
- 96 testes passando, nenhum tocando a rede.
- Instalação no Mac resolvida com `uv`, que baixa o Python sozinho.

## O que falta: um passo

**Colocar a senha de app no `.env` e fazer o primeiro envio real.**

```bash
cd ~/Documents/central/automacoes/mala-direta-pdf
git pull
cp .env.exemplo .env       # se ainda não existir
nano .env                  # ver "armadilhas" abaixo sobre o TextEdit
```

Troque `SMTP_SENHA=cole-aqui-as-16-letras` pela senha de app gerada **na conta
`veronica@ayatech.co`** em https://myaccount.google.com/apppasswords, sem os
espaços. No nano, salve com `Ctrl + O`, Enter, e saia com `Ctrl + X`.

Confirme que a troca pegou (este comando não mostra a senha):

```bash
grep -c "^SMTP_SENHA=cole-aqui" .env     # 0 = está preenchida
```

Depois, o teste real com uma planilha só sua:

```bash
printf 'Nome,Sobrenome,E-mail\nVeronica,Graciano,veronica@ayatech.co\n' > teste.csv

uv run mala-direta --config certificado-incompany/config.toml \
  --planilha teste.csv enviar --confirmar
```

No e-mail recebido, confira: remetente `no-reply@ayatech.co` (e não a conta
pessoal), anexo abre, nome centralizado no certificado.

## Decisões tomadas, e por quê

- **Remetente no-reply com contato por WhatsApp.** O texto do e-mail não promete
  resposta e aponta o +55 27 3191-2610, clicável na versão HTML.
- **SMTP, não API.** `no-reply@ayatech.co` é alias de `veronica@ayatech.co`, que
  autentica; como o alias é da própria conta, o Google aceita sem código de
  confirmação. O canal por API existe implementado e desligado, para o caso de o
  Workspace bloquear senhas de app ou o volume passar da cota (~2.000/dia).
- **Os PDFs modelo ficam fora do Git.** O certificado em branco carrega a
  assinatura do coordenador e este repositório é público, com GitHub Pages
  ligado. Eles vivem em `certificado-*/modelos/`, ignorados pelo Git.
- **Fonte Instrument Sans Bold**, escolhida comparando cinco fontes livres com o
  texto impresso no próprio certificado. Vai junto do projeto, com licença OFL.
- **O modelo vazio do For Business foi gerado a partir do SVG da arte**, porque
  só veio o mockup preenchido. O procedimento virou
  `ferramentas/modelo_a_partir_do_svg.py`.
- **Data e carga horária não são colunas da planilha**, porque são iguais para a
  turma. Ficam em `[valores]` no config, ou em `--valor` na linha de comando, ou
  nos campos da interface web.

## Armadilhas já encontradas

| Sintoma | Causa e solução |
| --- | --- |
| `fatal: not a git repository` | O Terminal abre na pasta pessoal. Comece sempre com o `cd` acima |
| `command not found: python3.13` | Não instale Python: use `uv`, que baixa a versão certa |
| `Directory cannot be installed in editable mode` | pip antigo. Com `uv sync` o problema não existe |
| TextEdit sem botão de salvar | É `Cmd + S`. Mais previsível usar `nano .env` |
| `grep -c "cole-aqui" .env` devolve 1 mesmo após salvar | Há duas linhas com esse texto. Use `grep -c "^SMTP_SENHA=cole-aqui"` |
| `PDF modelo não encontrado` | Falta arrastar o certificado em branco para `certificado-*/modelos/` |
| `Preencha antes de continuar` | Algum valor de `[valores]` ainda está com texto de exemplo |

## Depois que o teste passar

1. **Enviar para a turma real**: troque `participantes.csv` pela exportação do
   formulário, rode sem `--confirmar` para simular, confira, e repita com
   `--confirmar`.
2. **Abrir o pull request** da branch para a `main`.
3. **Hospedar a interface web**, se a equipe for usar sem terminal. Exige, nesta
   ordem: mover a automação para um repositório privado (por causa dos modelos
   com assinatura), contratar hospedagem com disco persistente (o `registro.csv`
   precisa sobreviver a reinícios), subir com um worker só e HTTPS.
4. **Fonte original da identidade**, se um dia o arquivo `.ttf` aparecer: trocar
   em `fontes/` e o nome em `[[pdf.fontes]]`.

## Para quem for pedir ajuda ao Claude Code na máquina

Contexto útil para colar na primeira mensagem: Mac com Python 3.9 de sistema
(por isso `uv`), projeto em `~/Documents/central/automacoes/mala-direta-pdf`,
branch `claude/happy-galileo-wflp4x`, conta de envio `veronica@ayatech.co` com
alias `no-reply@ayatech.co`. O `README.md` tem a documentação técnica e o
`PRIMEIROS-PASSOS.md`, o passo a passo de instalação.
