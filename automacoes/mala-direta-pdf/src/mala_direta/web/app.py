"""Interface web: escolher o modelo, preencher os valores da turma, conferir e enviar.

Esta camada não tem regra de negócio. Ela recebe o formulário, monta uma Config
a partir do modelo escolhido e chama o mesmo `executar()` que a linha de comando
usa. Sem banco de dados: a sessão vive num cookie assinado e o andamento do
envio, em memória.
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from mala_direta.config import Config, carregar_credenciais_smtp
from mala_direta.envio import EnviadorEmail, EnviadorSmtp
from mala_direta.erros import MalaDiretaError
from mala_direta.pipeline import Resultado, Status, colunas_exigidas, executar
from mala_direta.planilha import ler_destinatarios
from mala_direta.web.modelos import Modelo, descobrir_modelos
from mala_direta.web.seguranca import (
    COOKIE,
    Autenticacao,
    LimitadorDeTentativas,
    carregar_autenticacao,
)

LIMITE_UPLOAD = 10 * 1024 * 1024
EXTENSOES = {".xlsx", ".xlsm", ".csv", ".tsv"}
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@dataclass
class Tarefa:
    """Andamento de um envio em curso, mantido em memória."""

    id: str
    modelo: str
    total: int
    resultados: list[Resultado] = field(default_factory=list)
    concluida: bool = False
    erro: str | None = None

    @property
    def linhas(self) -> list[dict[str, str]]:
        return [
            {
                "email": resultado.destinatario.email,
                "status": str(resultado.status),
                "detalhe": resultado.detalhe,
            }
            for resultado in self.resultados
        ]


def criar_app(
    raiz_modelos: Path | None = None,
    autenticacao: Autenticacao | None = None,
    criar_enviador: Callable[[], EnviadorEmail] | None = None,
) -> FastAPI:
    """Monta o app. Os parâmetros existem para os testes injetarem dublês."""
    raiz = (raiz_modelos or Path.cwd()).resolve()
    autenticacao = autenticacao or carregar_autenticacao()
    criar_enviador = criar_enviador or (lambda: EnviadorSmtp(carregar_credenciais_smtp()))

    app = FastAPI(title="Mala direta AYA", docs_url=None, redoc_url=None)
    limitador = LimitadorDeTentativas()
    tarefas: dict[str, Tarefa] = {}
    # Guardar a referência evita que o coletor de lixo mate o envio em andamento.
    em_execucao: set[asyncio.Task] = set()

    def usuario_da_sessao(request: Request) -> str | None:
        return autenticacao.ler_sessao(request.cookies.get(COOKIE))

    def exigir_usuario(request: Request) -> str:
        usuario = usuario_da_sessao(request)
        if not usuario:
            raise HTTPException(status_code=303, headers={"Location": "/entrar"})
        return usuario

    def modelos() -> dict[str, Modelo]:
        return descobrir_modelos(raiz)

    def modelo_escolhido(chave: str) -> Modelo:
        disponiveis = modelos()
        if chave not in disponiveis:
            raise MalaDiretaError(f"Modelo desconhecido: {chave}")
        return disponiveis[chave]

    @app.exception_handler(HTTPException)
    async def redirecionar_sem_sessao(request: Request, excecao: HTTPException):
        if excecao.status_code == 303:
            return RedirectResponse(excecao.headers["Location"], status_code=303)
        return JSONResponse({"erro": excecao.detail}, status_code=excecao.status_code)

    @app.exception_handler(MalaDiretaError)
    async def mostrar_erro_de_dominio(request: Request, excecao: MalaDiretaError):
        return TEMPLATES.TemplateResponse(
            request, "erro.html", {"mensagem": str(excecao)}, status_code=400
        )

    @app.get("/entrar", response_class=HTMLResponse)
    async def pagina_de_login(request: Request):
        if usuario_da_sessao(request):
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(request, "entrar.html", {"aviso": None})

    @app.post("/entrar", response_class=HTMLResponse)
    async def autenticar(request: Request, usuario: str = Form(...), senha: str = Form(...)):
        origem = request.client.host if request.client else "desconhecido"
        if limitador.bloqueado(origem):
            return TEMPLATES.TemplateResponse(
                request,
                "entrar.html",
                {"aviso": "Muitas tentativas. Espere alguns minutos e tente de novo."},
                status_code=429,
            )

        if not autenticacao.verificar(usuario, senha):
            limitador.registrar_falha(origem)
            return TEMPLATES.TemplateResponse(
                request,
                "entrar.html",
                {"aviso": "Usuário ou senha incorretos."},
                status_code=401,
            )

        limitador.limpar(origem)
        resposta = RedirectResponse("/", status_code=303)
        resposta.set_cookie(
            COOKIE,
            autenticacao.criar_sessao(usuario),
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=autenticacao.duracao_horas * 3600,
        )
        return resposta

    @app.post("/sair")
    async def sair():
        resposta = RedirectResponse("/entrar", status_code=303)
        resposta.delete_cookie(COOKIE)
        return resposta

    @app.get("/", response_class=HTMLResponse)
    async def painel(request: Request):
        usuario = exigir_usuario(request)
        return TEMPLATES.TemplateResponse(
            request,
            "painel.html",
            {"usuario": usuario, "modelos": list(modelos().values())},
        )

    @app.post("/amostra")
    async def amostra(
        request: Request,
        modelo: str = Form(...),
        planilha: UploadFile = File(...),
    ):
        exigir_usuario(request)
        escolhido = modelo_escolhido(modelo)
        temporario = Path(tempfile.mkdtemp(prefix="mala-direta-"))
        try:
            config = _preparar(
                escolhido,
                await _valores_do_formulario(request),
                await _salvar(planilha, temporario),
            )
            resumo = executar(config, apenas_gerar=True, limite=1)
            resultado = resumo.resultados[0]
            if resultado.status is Status.ERRO or resultado.arquivo is None:
                raise MalaDiretaError(resultado.detalhe or "Não foi possível gerar a amostra.")
            return Response(
                resultado.arquivo.read_bytes(),
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="amostra-{modelo}.pdf"'},
            )
        finally:
            shutil.rmtree(temporario, ignore_errors=True)

    @app.post("/enviar", response_class=HTMLResponse)
    async def enviar(
        request: Request,
        modelo: str = Form(...),
        planilha: UploadFile = File(...),
        confirmar: str = Form(default=""),
    ):
        exigir_usuario(request)
        escolhido = modelo_escolhido(modelo)
        if confirmar != "sim":
            raise MalaDiretaError(
                "Marque a confirmação antes de enviar. Sem ela, nada é disparado."
            )

        temporario = Path(tempfile.mkdtemp(prefix="mala-direta-"))
        config = _preparar(
            escolhido, await _valores_do_formulario(request), await _salvar(planilha, temporario)
        )

        # Validação síncrona: a pessoa vê o erro na hora, antes de começar o lote.
        destinatarios = ler_destinatarios(config.planilha, colunas_exigidas(config))
        tarefa = Tarefa(
            id=secrets.token_urlsafe(8), modelo=escolhido.nome, total=len(destinatarios)
        )
        tarefas[tarefa.id] = tarefa

        execucao = asyncio.create_task(_rodar(tarefa, config, criar_enviador, temporario))
        em_execucao.add(execucao)
        execucao.add_done_callback(em_execucao.discard)
        return RedirectResponse(f"/envio/{tarefa.id}", status_code=303)

    @app.get("/envio/{identificador}", response_class=HTMLResponse)
    async def acompanhar(request: Request, identificador: str):
        exigir_usuario(request)
        tarefa = tarefas.get(identificador)
        if tarefa is None:
            raise MalaDiretaError("Envio não encontrado. Ele expira quando o serviço reinicia.")
        return TEMPLATES.TemplateResponse(request, "envio.html", {"tarefa": tarefa})

    @app.get("/envio/{identificador}/estado")
    async def estado(request: Request, identificador: str):
        exigir_usuario(request)
        tarefa = tarefas.get(identificador)
        if tarefa is None:
            return JSONResponse({"erro": "envio não encontrado"}, status_code=404)
        return JSONResponse(
            {
                "total": tarefa.total,
                "processados": len(tarefa.resultados),
                "concluida": tarefa.concluida,
                "erro": tarefa.erro,
                "linhas": tarefa.linhas,
            }
        )

    @app.get("/registro/{chave}")
    async def baixar_registro(request: Request, chave: str):
        exigir_usuario(request)
        registro = modelo_escolhido(chave).config.envio.registro
        if not registro.is_file():
            raise MalaDiretaError("Ainda não há registro de envios para este modelo.")
        return Response(
            registro.read_bytes(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="registro-{chave}.csv"'},
        )

    return app


async def _rodar(
    tarefa: Tarefa,
    config: Config,
    criar_enviador: Callable[[], EnviadorEmail],
    temporario: Path,
) -> None:
    def trabalho() -> None:
        enviador = criar_enviador()
        try:
            executar(config, enviador, ao_progredir=tarefa.resultados.append)
        finally:
            enviador.fechar()

    try:
        await asyncio.to_thread(trabalho)
    except MalaDiretaError as erro:
        tarefa.erro = str(erro)
    finally:
        tarefa.concluida = True
        shutil.rmtree(temporario, ignore_errors=True)


def _preparar(modelo: Modelo, valores: dict[str, str], planilha: Path) -> Config:
    """Config do modelo com a planilha enviada e os valores digitados na interface."""
    config = modelo.config.model_copy(deep=True)
    config.planilha.arquivo = planilha
    config.valores.update({nome: valor for nome, valor in valores.items() if valor.strip()})
    return config


async def _valores_do_formulario(request: Request) -> dict[str, str]:
    """Lê os campos enviados como valor:<coluna>, um por campo fixo do modelo."""
    formulario = await request.form()
    return {
        chave.removeprefix("valor:"): str(valor)
        for chave, valor in formulario.items()
        if chave.startswith("valor:")
    }


async def _salvar(arquivo: UploadFile, destino: Path) -> Path:
    """Grava o upload em disco, recusando formato desconhecido e arquivo grande."""
    nome = Path(arquivo.filename or "planilha")
    if nome.suffix.lower() not in EXTENSOES:
        aceitos = ", ".join(sorted(EXTENSOES))
        raise MalaDiretaError(f"Formato não suportado: {nome.suffix or nome.name}. Use {aceitos}.")

    caminho = destino / f"planilha{nome.suffix.lower()}"
    tamanho = 0
    with caminho.open("wb") as saida:
        while bloco := await arquivo.read(64 * 1024):
            tamanho += len(bloco)
            if tamanho > LIMITE_UPLOAD:
                raise MalaDiretaError("Planilha maior que 10 MB.")
            saida.write(bloco)
    return caminho
