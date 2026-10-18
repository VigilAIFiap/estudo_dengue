"""API analítica da plataforma de vigilância da dengue.

Executar a partir da raiz do projeto:
    uvicorn api.main:app --port 8000
"""

from __future__ import annotations

import io
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from . import analytics as a
from . import schemas as s
from .assist import FERRAMENTAS, responder
from .dataset import CLASSIFICACAO, CONFIRMADOS, UF_NOME, Dataset, carregar

load_dotenv()

RAIZ = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("DENGUE_DATA_DIR", RAIZ / "dados"))
ASSIST_MODELO = os.environ.get("ASSIST_MODEL", "claude-sonnet-5-5")
ORIGENS = [o for o in os.environ.get("API_CORS_ORIGINS", "http://localhost:3000").split(",") if o]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.dataset = carregar(DATA_DIR)
    yield


app = FastAPI(
    title="Vigilância Dengue — API analítica",
    version="1.0.0",
    lifespan=lifespan,
    responses={400: {"model": s.Erro}, 404: {"model": s.Erro}},
)
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(ValueError)
async def erro_validacao(_: Request, erro: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(erro)})


@app.exception_handler(LookupError)
async def erro_busca(_: Request, erro: LookupError):
    return JSONResponse(status_code=404, content={"detail": str(erro) or "Registro não encontrado."})


def dataset(request: Request) -> Dataset:
    return request.app.state.dataset


def filtros(
    inicio: date | None = None,
    fim: date | None = None,
    uf: Annotated[list[str], Query()] = [],  # noqa: B006 — FastAPI copia o padrão
    municipio: int | None = None,
    classificacao: Annotated[list[int], Query()] = [],  # noqa: B006
) -> a.Filtros:
    ufs = tuple(sorted({u.upper() for u in uf}))
    invalidas = [u for u in ufs if u not in UF_NOME]
    if invalidas:
        raise HTTPException(400, f"UF inválida: {', '.join(invalidas)}")
    codigos = tuple(sorted(set(classificacao)))
    invalidos = [c for c in codigos if c not in CLASSIFICACAO]
    if invalidos:
        raise HTTPException(400, f"Classificação inválida: {invalidos}")
    if inicio and fim and inicio > fim:
        raise HTTPException(400, "A data inicial deve ser anterior ou igual à final.")
    return a.Filtros(inicio=inicio, fim=fim, ufs=ufs, municipio=municipio, classificacoes=codigos)


DS = Annotated[Dataset, Depends(dataset)]
F = Annotated[a.Filtros, Depends(filtros)]


@app.get("/api/meta", response_model=s.Meta)
def meta(ds: DS):
    inicio, fim = a.cobertura(ds)
    # Padrão: semanas epidemiológicas do último ano com dados.
    ano_fim = ds.notificacoes.loc[ds.notificacoes["data"] == ds.notificacoes["data"].max(), "ano_epi"].iloc[0]
    padrao_inicio = ds.notificacoes.loc[ds.notificacoes["ano_epi"] == ano_fim, "inicio_semana"].min().date()
    return {
        "cobertura_inicio": inicio,
        "cobertura_fim": fim,
        "padrao_inicio": padrao_inicio,
        "padrao_fim": fim,
        "defasagem_dias": (date.today() - fim).days,
        "carregado_em": ds.carregado_em,
        "arquivos": [
            {"nome": n, "bytes": b, "modificado_em": datetime.fromtimestamp(m, tz=timezone.utc)}
            for n, b, m in ds.arquivos
        ],
        "linhas_descartadas": ds.linhas_descartadas,
        "total_notificacoes": len(ds.notificacoes),
        "ufs": [{"sigla": k, "nome": v} for k, v in sorted(UF_NOME.items(), key=lambda x: x[1])],
        "classificacoes": [{"codigo": k, "rotulo": v} for k, v in CLASSIFICACAO.items()],
        "confirmados_codigos": list(CONFIRMADOS),
        "niveis": list(a.NIVEIS),
    }


@app.get("/api/visao-geral", response_model=s.VisaoGeral)
def visao_geral(ds: DS, f: F):
    tabela, q1 = a.criticidade(ds, f)
    topo = a.ranking(ds, f, pagina=1, tamanho=10, ordenar="score_criticidade", direcao="desc", busca=None, niveis=())
    return {
        **a.visao_geral(ds, f),
        **a.insights_e_alertas(ds, f),
        "niveis": a.niveis_distribuicao(tabela),
        "top_municipios": topo["itens"],
        "metodologia": a.metodologia_score(q1),
    }


@app.get("/api/series", response_model=list[s.PontoSerie])
def series(ds: DS, f: F, granularidade: Literal["semana", "mes"] = "semana"):
    return a.serie(ds, f, granularidade)


@app.get("/api/series/anual", response_model=s.ComparacaoAnual)
def series_anual(ds: DS, f: F):
    return a.comparacao_anual(ds, f)


@app.get("/api/distribuicoes", response_model=s.Distribuicoes)
def distribuicoes(ds: DS, f: F):
    return a.distribuicoes(ds, f)


@app.get("/api/municipios", response_model=s.Ranking)
def municipios(
    ds: DS,
    f: F,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 25,
    ordenar: str = "score_criticidade",
    direcao: Literal["asc", "desc"] = "desc",
    busca: Annotated[str | None, Query(max_length=80)] = None,
    nivel: Annotated[list[str], Query()] = [],  # noqa: B006
):
    invalidos = [n for n in nivel if n not in a.NIVEIS]
    if invalidos:
        raise HTTPException(400, f"Nível inválido: {invalidos}")
    resultado = a.ranking(
        ds, f, pagina=pagina, tamanho=tamanho, ordenar=ordenar, direcao=direcao, busca=busca, niveis=tuple(nivel)
    )
    return {**resultado, "metodologia": a.metodologia_score(resultado["q1"])}


@app.get("/api/municipios/busca", response_model=list[s.MunicipioBusca])
def municipios_busca(ds: DS, q: Annotated[str, Query(min_length=2, max_length=80)]):
    return a.buscar_municipios(ds, q)


@app.get("/api/municipios/{id_municip}", response_model=s.DetalheMunicipio)
def municipio(ds: DS, f: F, id_municip: int):
    try:
        return a.detalhe_municipio(ds, f, id_municip)
    except KeyError:
        raise HTTPException(404, f"Município {id_municip} não existe em municipios.csv.") from None


@app.get("/api/mapa", response_model=s.Mapa)
def mapa(ds: DS, f: F):
    return a.mapa(ds, f)


@app.get("/api/previsao", response_model=s.Previsao)
def previsao(ds: DS, f: F):
    return a.previsao(ds, f)


@app.get("/api/pacientes/status", response_model=s.PacientesStatus)
def pacientes_status(ds: DS):
    return a.pacientes_status(ds)


def _csv(frame, nome: str) -> StreamingResponse:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, sep=";", decimal=",")
    conteudo = "﻿" + buffer.getvalue()  # BOM para o Excel reconhecer UTF-8
    return StreamingResponse(
        iter([conteudo.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.get("/api/export/agregado.csv")
def export_agregado(ds: DS, f: F):
    return _csv(a.exportar_agregado(ds, f), "dengue_mes_municipio.csv")


@app.get("/api/export/municipios.csv")
def export_municipios(ds: DS, f: F):
    return _csv(a.exportar_ranking(ds, f), "dengue_criticidade_municipios.csv")


@app.get("/api/export/serie.csv")
def export_serie(ds: DS, f: F, granularidade: Literal["semana", "mes"] = "semana"):
    import pandas as pd

    return _csv(pd.DataFrame(a.serie(ds, f, granularidade)), f"dengue_serie_{granularidade}.csv")


@app.get("/api/assist/status", response_model=s.AssistStatus)
def assist_status():
    configurado = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "configurado": configurado,
        "modelo": ASSIST_MODELO if configurado else None,
        "ferramentas": [t["name"] for t in FERRAMENTAS],
    }


@app.post("/api/assist", response_model=s.RespostaAssist, responses={503: {"model": s.Erro}})
def assist(ds: DS, pedido: s.PedidoAssist):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "Provedor de IA não configurado: defina ANTHROPIC_API_KEY no .env da API.")
    if not pedido.mensagens or pedido.mensagens[-1].papel != "usuario":
        raise HTTPException(400, "A última mensagem deve ser do usuário.")
    import anthropic

    cliente = anthropic.Anthropic()
    try:
        return responder(ds, [m.model_dump() for m in pedido.mensagens], cliente.messages.create, ASSIST_MODELO)
    except anthropic.APIError as erro:
        raise HTTPException(502, f"Falha no provedor de IA: {erro.message}") from erro
