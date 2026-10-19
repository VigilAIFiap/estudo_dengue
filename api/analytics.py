"""Consultas analíticas sobre o Dataset carregado.

Todas as funções são puras: recebem o Dataset e os filtros e retornam
estruturas serializáveis. Nenhum cálculo epidemiológico é feito no frontend.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from criticidade import (  # noqa: E402
    CORTES,
    PESO_HOSPITALIZACAO,
    PESO_OBITO,
    PESO_VOLUME,
    PISO_CASOS,
    criticality_from_notifications,
)

from .dataset import CLASSIFICACAO, EVOLUCAO, HOSPITALIZACAO, UF_NOME, Dataset, semana_epidemiologica  # noqa: E402

NIVEIS = tuple(nivel for nivel, _ in CORTES)
DESLOCAMENTO_ANUAL = timedelta(days=364)  # 52 semanas: preserva as semanas epidemiológicas
LIMIAR_ALERTA_AUMENTO = 1.0  # +100%
LIMIAR_ALERTA_VOLUME = 100


@dataclass(frozen=True)
class Filtros:
    inicio: date | None = None
    fim: date | None = None
    ufs: tuple[str, ...] = ()
    municipio: int | None = None
    classificacoes: tuple[int, ...] = ()


def cobertura(ds: Dataset) -> tuple[date, date]:
    datas = ds.notificacoes["data"]
    return datas.min().date(), datas.max().date()


def intervalo(ds: Dataset, f: Filtros) -> tuple[date, date]:
    """Intervalo efetivo: filtros limitados à cobertura dos dados."""
    minimo, maximo = cobertura(ds)
    inicio = max(f.inicio or minimo, minimo)
    fim = min(f.fim or maximo, maximo)
    if inicio > fim:
        raise ValueError("O intervalo selecionado não tem dados: a data inicial é posterior à final.")
    return inicio, fim


def mascara(ds: Dataset, f: Filtros, *, datas: bool = True, municipio: bool = True) -> np.ndarray:
    df = ds.notificacoes
    m = np.ones(len(df), dtype=bool)
    if datas:
        inicio, fim = intervalo(ds, f)
        valores = df["data"].to_numpy()
        m &= (valores >= np.datetime64(inicio)) & (valores <= np.datetime64(fim))
    if f.ufs:
        m &= df["uf"].isin(f.ufs).to_numpy()
    if municipio and f.municipio is not None:
        m &= df["id_municip"].to_numpy() == f.municipio
    if f.classificacoes:
        m &= np.isin(df["classi"].to_numpy(), f.classificacoes)
    return m


def _totais(df: pd.DataFrame) -> dict[str, int]:
    return {
        "notificacoes": int(len(df)),
        "confirmados": int(df["confirmado"].sum()),
        "graves": int(df["grave"].sum()),
        "obitos": int(df["obito_dengue"].sum()),
        "obitos_investigacao": int(df["obito_investigacao"].sum()),
        "hospitalizacoes": int(df["hospitalizado"].sum()),
        "municipios": int(df["id_municip"].nunique()),
    }


def _variacao(atual: int, anterior: int) -> float | None:
    if anterior == 0:
        return None
    return round((atual - anterior) / anterior * 100, 1)


def periodo_anterior(ds: Dataset, f: Filtros) -> tuple[date, date] | None:
    """Mesmo intervalo 52 semanas antes, se estiver inteiramente coberto pelos dados."""
    inicio, fim = intervalo(ds, f)
    anterior = (inicio - DESLOCAMENTO_ANUAL, fim - DESLOCAMENTO_ANUAL)
    if anterior[0] < cobertura(ds)[0]:
        return None
    return anterior


@lru_cache(maxsize=256)
def visao_geral(ds: Dataset, f: Filtros) -> dict:
    df = ds.notificacoes
    atual = _totais(df.loc[mascara(ds, f)])
    inicio, fim = intervalo(ds, f)
    anterior_periodo = periodo_anterior(ds, f)
    comparacao = None
    if anterior_periodo is not None:
        anterior = _totais(
            df.loc[mascara(ds, replace(f, inicio=anterior_periodo[0], fim=anterior_periodo[1]))]
        )
        comparacao = {
            "inicio": anterior_periodo[0],
            "fim": anterior_periodo[1],
            "totais": anterior,
            "variacao_pct": {k: _variacao(atual[k], anterior[k]) for k in atual},
        }
    return {
        "inicio": inicio,
        "fim": fim,
        "totais": atual,
        "comparacao": comparacao,
        "motivo_sem_comparacao": None
        if comparacao
        else "O mesmo intervalo 52 semanas antes não está inteiramente coberto pelos dados.",
    }


def serie(ds: Dataset, f: Filtros, granularidade: str) -> list[dict]:
    if granularidade not in ("semana", "mes"):
        raise ValueError("granularidade deve ser 'semana' ou 'mes'.")
    df = ds.notificacoes.loc[mascara(ds, f)]
    if df.empty:
        return []
    inicio, fim = intervalo(ds, f)
    chave = "inicio_semana" if granularidade == "semana" else "mes"
    g = (
        df.groupby(chave, observed=True)
        .agg(
            notificacoes=("id_municip", "size"),
            confirmados=("confirmado", "sum"),
            graves=("grave", "sum"),
            hospitalizacoes=("hospitalizado", "sum"),
            obitos=("obito_dengue", "sum"),
        )
        .sort_index()
    )
    # Períodos sem notificações dentro do intervalo aparecem como zero.
    freq = "W-SUN" if granularidade == "semana" else "MS"
    g = g.reindex(pd.date_range(g.index.min(), pd.Timestamp(fim), freq=freq), fill_value=0)
    ano_epi, semana_epi, _ = semana_epidemiologica(pd.Series(g.index))
    linhas = []
    for (periodo_inicio, r), ano, semana in zip(g.iterrows(), ano_epi, semana_epi):
        periodo_fim = (
            periodo_inicio + pd.Timedelta(days=6)
            if granularidade == "semana"
            else periodo_inicio + pd.offsets.MonthEnd(0)
        )
        linhas.append(
            {
                "periodo": f"SE {semana}/{ano}" if granularidade == "semana" else periodo_inicio.strftime("%m/%Y"),
                "inicio": periodo_inicio.date(),
                "fim": periodo_fim.date(),
                "parcial": periodo_inicio.date() < inicio or periodo_fim.date() > fim,
                **{k: int(r[k]) for k in g.columns},
            }
        )
    return linhas


@lru_cache(maxsize=64)
def comparacao_anual(ds: Dataset, f: Filtros) -> dict:
    """Notificações e confirmados por semana epidemiológica, um traço por ano.

    Ignora o intervalo de datas (compara anos inteiros); aplica UF, município
    e classificação.
    """
    df = ds.notificacoes.loc[mascara(ds, f, datas=False)]
    g = (
        df.groupby(["ano_epi", "semana_epi"])
        .agg(notificacoes=("id_municip", "size"), confirmados=("confirmado", "sum"))
        .reset_index()
    )
    _, maximo = cobertura(ds)
    anos = []
    for ano, bloco in g.groupby("ano_epi"):
        ultima = int(bloco["semana_epi"].max())
        inicio_ultima = df.loc[(df["ano_epi"] == ano) & (df["semana_epi"] == ultima), "inicio_semana"].iloc[0]
        anos.append(
            {
                "ultima_semana_parcial": bool((inicio_ultima + pd.Timedelta(days=6)).date() > maximo),
                "ano": int(ano),
                "semanas": [
                    {"semana": int(r.semana_epi), "notificacoes": int(r.notificacoes), "confirmados": int(r.confirmados)}
                    for r in bloco.itertuples()
                ],
                "ultima_semana": ultima,
            }
        )
    return {"anos": anos, "ultima_data": maximo}


def distribuicoes(ds: Dataset, f: Filtros) -> dict:
    df = ds.notificacoes.loc[mascara(ds, f)]

    def contar(coluna: str, rotulos: dict[int, str]) -> list[dict]:
        contagem = df[coluna].value_counts()
        total = int(contagem.sum())
        return [
            {
                "codigo": int(codigo),
                "rotulo": rotulos.get(int(codigo), f"Código {int(codigo)}"),
                "total": int(n),
                "pct": round(n / total * 100, 2) if total else 0.0,
            }
            for codigo, n in contagem.items()
        ]

    return {
        "classificacao": contar("classi", CLASSIFICACAO),
        "evolucao": contar("evolucao", EVOLUCAO),
        "hospitalizacao": contar("hospitaliz", HOSPITALIZACAO),
    }


@lru_cache(maxsize=64)
def criticidade(ds: Dataset, f: Filtros) -> tuple[pd.DataFrame, float]:
    """Score por município sobre o recorte filtrado (sem filtro de município).

    Óbito no score segue a regra de negócio para EVOLUCAO 2 ou 3. O score é relativo: a
    normalização min-max ocorre entre os municípios do recorte.
    """
    df = ds.notificacoes.loc[mascara(ds, f, municipio=False)]
    if df.empty:
        raise ValueError("Não há notificações no recorte selecionado.")
    entrada = pd.DataFrame(
        {
            "ID_MUNICIP": df["id_municip"].to_numpy(),
            "obito": np.isin(df["evolucao"].to_numpy(), (2, 3)).astype(int),
            "hospitalizado": df["hospitalizado"].astype(int).to_numpy(),
            "UF": df["uf"].astype(str).to_numpy(),
        }
    )
    score, q1 = criticality_from_notifications(entrada)
    extras = df.groupby("id_municip").agg(
        confirmados=("confirmado", "sum"),
        graves=("grave", "sum"),
        obitos_dengue=("obito_dengue", "sum"),
    )
    todos = (
        df.groupby("id_municip")
        .agg(
            notificacoes=("id_municip", "size"),
            hospitalizacoes=("hospitalizado", "sum"),
        )
        .join(extras)
        .join(ds.municipios[["nome", "uf", "latitude", "longitude", "capital"]])
    )
    score = score.set_index("id_municip")[
        ["score_criticidade", "nivel", "norm_log_casos", "norm_taxa_obito", "norm_taxa_hospitalizacao", "taxa_obito", "obitos"]
    ]
    resultado = todos.join(score, how="left").rename(columns={"obitos": "obitos_score"})
    resultado["taxa_hospitalizacao"] = resultado["hospitalizacoes"] / resultado["notificacoes"]
    resultado["letalidade"] = np.where(
        resultado["confirmados"] > 0, resultado["obitos_dengue"] / resultado["confirmados"], np.nan
    )
    resultado = resultado.sort_values(["score_criticidade", "notificacoes"], ascending=False, na_position="last")
    resultado["posicao"] = np.where(
        resultado["score_criticidade"].notna(),
        resultado["score_criticidade"].rank(method="first", ascending=False),
        np.nan,
    )
    return resultado, q1


COLUNAS_ORDENAVEIS = {
    "nome", "uf", "notificacoes", "confirmados", "graves", "obitos_dengue",
    "hospitalizacoes", "taxa_hospitalizacao", "letalidade", "score_criticidade",
}


def _linha_municipio(id_municip: int, r: pd.Series) -> dict:
    def num(v):
        return None if pd.isna(v) else float(v)

    return {
        "id_municip": int(id_municip),
        "nome": r["nome"],
        "uf": r["uf"],
        "capital": bool(r["capital"]),
        "notificacoes": int(r["notificacoes"]),
        "confirmados": int(r["confirmados"]),
        "graves": int(r["graves"]),
        "obitos_dengue": int(r["obitos_dengue"]),
        "hospitalizacoes": int(r["hospitalizacoes"]),
        "taxa_hospitalizacao": num(r["taxa_hospitalizacao"]),
        "letalidade": num(r["letalidade"]),
        "score": num(r["score_criticidade"]),
        "nivel": None if pd.isna(r["nivel"]) else r["nivel"],
        "posicao": None if pd.isna(r["posicao"]) else int(r["posicao"]),
    }


def ranking(
    ds: Dataset,
    f: Filtros,
    *,
    pagina: int,
    tamanho: int,
    ordenar: str,
    direcao: str,
    busca: str | None,
    niveis: tuple[str, ...],
) -> dict:
    if ordenar not in COLUNAS_ORDENAVEIS:
        raise ValueError(f"Coluna de ordenação inválida: {ordenar}")
    if direcao not in ("asc", "desc"):
        raise ValueError("direcao deve ser 'asc' ou 'desc'.")
    tabela, q1 = criticidade(ds, f)
    if busca:
        termo = _sem_acento(busca)
        tabela = tabela[tabela["nome"].map(_sem_acento).str.contains(termo, regex=False)]
    if niveis:
        tabela = tabela[tabela["nivel"].isin(niveis)]
    tabela = tabela.sort_values(ordenar, ascending=direcao == "asc", na_position="last", kind="stable")
    total = len(tabela)
    pagina_df = tabela.iloc[(pagina - 1) * tamanho : pagina * tamanho]
    return {
        "total": total,
        "pagina": pagina,
        "tamanho": tamanho,
        "q1": q1,
        "itens": [_linha_municipio(i, r) for i, r in pagina_df.iterrows()],
    }


def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn"
    )


def buscar_municipios(ds: Dataset, termo: str, limite: int = 12) -> list[dict]:
    termo = _sem_acento(termo.strip())
    if len(termo) < 2:
        return []
    com_dados = ds.notificacoes["id_municip"].value_counts()
    m = ds.municipios.loc[ds.municipios.index.isin(com_dados.index)]
    nomes = m["nome"].map(_sem_acento)
    achados = m[nomes.str.contains(termo, regex=False)].copy()
    achados["comeca"] = nomes[achados.index].str.startswith(termo)
    achados["volume"] = com_dados.reindex(achados.index)
    achados = achados.sort_values(["comeca", "volume"], ascending=False).head(limite)
    return [
        {"id_municip": int(i), "nome": r["nome"], "uf": r["uf"]} for i, r in achados.iterrows()
    ]


def niveis_distribuicao(tabela: pd.DataFrame) -> list[dict]:
    pontuados = tabela[tabela["nivel"].notna()]
    contagem = pontuados.groupby("nivel").agg(
        municipios=("nivel", "size"), notificacoes=("notificacoes", "sum"), obitos=("obitos_dengue", "sum")
    )
    linhas = [
        {
            "nivel": nivel,
            "municipios": int(contagem.loc[nivel, "municipios"]) if nivel in contagem.index else 0,
            "notificacoes": int(contagem.loc[nivel, "notificacoes"]) if nivel in contagem.index else 0,
            "obitos": int(contagem.loc[nivel, "obitos"]) if nivel in contagem.index else 0,
        }
        for nivel in NIVEIS
    ]
    sem_score = tabela[tabela["nivel"].isna()]
    linhas.append(
        {
            "nivel": "Sem score",
            "municipios": int(len(sem_score)),
            "notificacoes": int(sem_score["notificacoes"].sum()),
            "obitos": int(sem_score["obitos_dengue"].sum()),
        }
    )
    return linhas


def metodologia_score(q1: float) -> dict:
    return {
        "pesos": {"volume_log": PESO_VOLUME, "taxa_obito": PESO_OBITO, "taxa_hospitalizacao": PESO_HOSPITALIZACAO},
        "piso_casos": PISO_CASOS,
        "q1": q1,
        "cortes": [{"nivel": n, "minimo": None if c == float("-inf") else c} for n, c in CORTES],
    }


def detalhe_municipio(ds: Dataset, f: Filtros, id_municip: int) -> dict:
    if id_municip not in ds.municipios.index:
        raise KeyError(id_municip)
    tabela, q1 = criticidade(ds, f)
    if id_municip not in tabela.index:
        raise LookupError("O município não tem notificações no recorte selecionado.")
    linha = _linha_municipio(id_municip, tabela.loc[id_municip])
    r = tabela.loc[id_municip]
    componentes = None
    if pd.notna(r["score_criticidade"]):
        componentes = {
            "volume": round(float(r["norm_log_casos"]) * PESO_VOLUME * 100, 1),
            "obito": round(float(r["norm_taxa_obito"]) * PESO_OBITO * 100, 1),
            "hospitalizacao": round(float(r["norm_taxa_hospitalizacao"]) * PESO_HOSPITALIZACAO * 100, 1),
            "abaixo_piso": bool(r["notificacoes"] < PISO_CASOS),
        }
    pontuados = int(tabela["score_criticidade"].notna().sum())
    return {
        **linha,
        "latitude": float(r["latitude"]),
        "longitude": float(r["longitude"]),
        "componentes": componentes,
        "municipios_pontuados": pontuados,
        "q1": q1,
        "serie": serie(ds, replace(f, municipio=id_municip), "semana"),
    }


CAMADAS = {
    "notificacoes": "notificacoes",
    "confirmados": "confirmados",
    "obitos": "obitos_dengue",
    "hospitalizacoes": "hospitalizacoes",
    "score": "score_criticidade",
}


def mapa(ds: Dataset, f: Filtros) -> dict:
    tabela, q1 = criticidade(ds, f)
    pontos = [
        {
            "id": int(i),
            "nome": r["nome"],
            "uf": r["uf"],
            "lat": round(float(r["latitude"]), 4),
            "lon": round(float(r["longitude"]), 4),
            "notificacoes": int(r["notificacoes"]),
            "confirmados": int(r["confirmados"]),
            "obitos": int(r["obitos_dengue"]),
            "hospitalizacoes": int(r["hospitalizacoes"]),
            "score": None if pd.isna(r["score_criticidade"]) else float(r["score_criticidade"]),
            "nivel": None if pd.isna(r["nivel"]) else r["nivel"],
        }
        for i, r in tabela.iterrows()
    ]
    por_uf = (
        tabela.groupby("uf")
        .agg(
            notificacoes=("notificacoes", "sum"),
            confirmados=("confirmados", "sum"),
            obitos=("obitos_dengue", "sum"),
            hospitalizacoes=("hospitalizacoes", "sum"),
            municipios=("notificacoes", "size"),
            criticos=("nivel", lambda s: int((s == "Crítico").sum())),
        )
        .reset_index()
    )
    ufs = [
        {"uf": r.uf, "nome": UF_NOME[r.uf], **{k: int(getattr(r, k)) for k in ("notificacoes", "confirmados", "obitos", "hospitalizacoes", "municipios", "criticos")}}
        for r in por_uf.itertuples()
    ]
    return {"pontos": pontos, "ufs": ufs, "q1": q1}


def _fmt(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{_fmt(n)} {singular if n == 1 else plural}"


def _pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + "%"


def insights_e_alertas(ds: Dataset, f: Filtros) -> dict:
    """Achados descritivos com critério explícito. Nenhum é causal."""
    tabela, _ = criticidade(ds, f)
    geral = visao_geral(ds, f)
    total = geral["totais"]["notificacoes"]
    insights: list[dict] = []
    alertas: list[dict] = []
    if total == 0:
        return {"insights": insights, "alertas": alertas}

    topo = tabela.sort_values("notificacoes", ascending=False)
    lider = topo.iloc[0]
    insights.append(
        {
            "id": "maior_volume",
            "titulo": f"{lider['nome']} ({lider['uf']}) concentra {_pct(lider['notificacoes'] / total * 100)} das notificações",
            "detalhe": f"{_fmt(lider['notificacoes'])} de {_fmt(total)} notificações no recorte.",
            "origem": "Contagem de notificações por município notificador (ID_MUNICIP).",
            "municipio": int(topo.index[0]),
        }
    )
    top10 = topo["notificacoes"].head(10).sum() / total * 100
    insights.append(
        {
            "id": "concentracao",
            "titulo": f"Os 10 municípios com mais notificações somam {_pct(top10)} do total",
            "detalhe": f"{_plural(len(tabela), 'município notificou', 'municípios notificaram')} ao menos um caso no recorte.",
            "origem": "Soma das 10 maiores contagens municipais dividida pelo total do recorte.",
            "municipio": None,
        }
    )
    pontuados = tabela[tabela["score_criticidade"].notna()]
    if not pontuados.empty:
        maior = pontuados.iloc[0]
        insights.append(
            {
                "id": "maior_score",
                "titulo": f"Maior score de criticidade: {maior['nome']} ({maior['uf']}), {str(maior['score_criticidade']).replace('.', ',')}",
                "detalhe": f"Nível {maior['nivel']}. Score relativo aos {len(pontuados)} municípios pontuados no recorte.",
                "origem": "Score do projeto: 50% volume (log), 30% taxa de óbito, 20% taxa de hospitalização.",
                "municipio": int(pontuados.index[0]),
            }
        )
    comparacao = geral["comparacao"]
    if comparacao and comparacao["variacao_pct"]["notificacoes"] is not None:
        v = comparacao["variacao_pct"]["notificacoes"]
        direcao = "acima" if v > 0 else "abaixo"
        insights.append(
            {
                "id": "variacao_anual",
                "titulo": f"Notificações {_pct(abs(v))} {direcao} do mesmo período de 52 semanas antes",
                "detalhe": f"{_fmt(total)} agora contra {_fmt(comparacao['totais']['notificacoes'])} entre "
                f"{comparacao['inicio'].strftime('%d/%m/%Y')} e {comparacao['fim'].strftime('%d/%m/%Y')}.",
                "origem": "Mesmas semanas epidemiológicas, deslocadas 364 dias. Dados recentes podem ser revisados para cima.",
                "municipio": None,
            }
        )

    # Alertas — critérios fixos e documentados.
    criticos = int((tabela["nivel"] == "Crítico").sum())
    if criticos:
        alertas.append(
            {
                "id": "criticos",
                "severidade": "Crítico",
                "titulo": f"{_plural(criticos, 'município', 'municípios')} em nível crítico",
                "criterio": "Score de criticidade ≥ 50 no recorte selecionado.",
            }
        )
    if comparacao:
        anterior = ds.notificacoes.loc[
            mascara(ds, replace(f, inicio=comparacao["inicio"], fim=comparacao["fim"]), municipio=False)
        ]["id_municip"].value_counts()
        atual = tabela["notificacoes"]
        base = anterior.reindex(atual.index).fillna(0)
        aumento = atual[(atual >= LIMIAR_ALERTA_VOLUME) & (base > 0) & ((atual - base) / base >= LIMIAR_ALERTA_AUMENTO)]
        if len(aumento):
            alertas.append(
                {
                    "id": "aumento",
                    "severidade": "Alto",
                    "titulo": f"{_plural(len(aumento), 'município dobrou', 'municípios dobraram')} as notificações em relação ao ano anterior",
                    "criterio": f"≥ {LIMIAR_ALERTA_VOLUME} notificações no recorte e aumento ≥ 100% sobre as mesmas semanas do ano anterior.",
                }
            )
    investigacao = geral["totais"]["obitos_investigacao"]
    if investigacao:
        alertas.append(
            {
                "id": "obitos_investigacao",
                "severidade": "Médio",
                "titulo": f"{_plural(investigacao, 'óbito', 'óbitos')} ainda em investigação",
                "criterio": "EVOLUCAO = 4. Podem ser reclassificados como óbito por dengue.",
            }
        )
    defasagem = (date.today() - cobertura(ds)[1]).days
    if defasagem > 30:
        alertas.append(
            {
                "id": "defasagem",
                "severidade": "Médio",
                "titulo": f"Última notificação na base é de {defasagem} dias atrás",
                "criterio": "Diferença entre hoje e a maior DT_NOTIFIC carregada maior que 30 dias.",
            }
        )
    return {"insights": insights, "alertas": alertas}


@lru_cache(maxsize=64)
def previsao(ds: Dataset, f: Filtros) -> dict:
    """Executa o módulo src/modelos/series_temporais sem alterar suas regras."""
    from modelos.series_temporais import forecast_monthly_cases, prepare_monthly_cases, rolling_backtest

    df = ds.notificacoes.loc[mascara(ds, f, datas=False)]
    entrada = pd.DataFrame({"DT_NOTIFIC": df["data"].to_numpy(), "CLASSI_FIN": df["classi"].astype(str).to_numpy()})
    referencia = pd.Timestamp(cobertura(ds)[1])
    base = {"data_referencia": referencia.date(), "historico": [], "previsao": [], "validacao": None}
    if entrada.empty:
        return {**base, "status": "indisponivel", "motivo": "Não há notificações no recorte selecionado."}
    try:
        observada = prepare_monthly_cases(entrada, as_of=referencia, min_months=1)
        base["historico"] = [{"mes": i.date(), "casos": int(v)} for i, v in observada.items()]
        mensal = prepare_monthly_cases(entrada, as_of=referencia)
    except ValueError as erro:
        return {**base, "status": "indisponivel", "motivo": str(erro)}
    try:
        tabela = forecast_monthly_cases(mensal, months=12)
        validacao = rolling_backtest(mensal, horizon=3, seasonal_period=12)
    except (ValueError, ImportError) as erro:
        return {**base, "status": "indisponivel", "motivo": f"O modelo não convergiu: {erro}"}
    base["previsao"] = [
        {
            "mes": i.date(),
            "previsao": int(r["PREVISAO"]),
            "inferior": float(r["LIMITE_INFERIOR_95"]),
            "superior": float(r["LIMITE_SUPERIOR_95"]),
        }
        for i, r in tabela.iterrows()
    ]
    base["validacao"] = validacao
    return {**base, "status": "disponivel", "motivo": None}


def pacientes_status(ds: Dataset) -> dict:
    from modelos.pacientes import FEATURE_COLUMNS

    necessarias = set(FEATURE_COLUMNS) | {"DT_NOTIFIC", "CLASSI_FIN", "HOSPITALIZ"}
    disponiveis = set(ds.colunas_disponiveis)
    if "NU_IDADE_N" in disponiveis:
        disponiveis.add("IDADE_ANOS")
    faltando = sorted(necessarias - disponiveis)
    return {
        "disponivel": not faltando,
        "colunas_faltando": faltando,
        "colunas_disponiveis": sorted(ds.colunas_disponiveis),
    }


def exportar_agregado(ds: Dataset, f: Filtros) -> pd.DataFrame:
    df = ds.notificacoes.loc[mascara(ds, f)]
    g = (
        df.groupby(["mes", "id_municip"], observed=True)
        .agg(
            notificacoes=("id_municip", "size"),
            confirmados=("confirmado", "sum"),
            graves=("grave", "sum"),
            obitos_dengue=("obito_dengue", "sum"),
            hospitalizacoes=("hospitalizado", "sum"),
        )
        .reset_index()
        .join(ds.municipios[["codigo_ibge", "nome", "uf"]], on="id_municip")
    )
    g["mes"] = g["mes"].dt.strftime("%Y-%m")
    return g[["mes", "uf", "codigo_ibge", "nome", "notificacoes", "confirmados", "graves", "obitos_dengue", "hospitalizacoes"]]


def exportar_ranking(ds: Dataset, f: Filtros) -> pd.DataFrame:
    tabela, _ = criticidade(ds, f)
    t = tabela.join(ds.municipios[["codigo_ibge"]])
    t["posicao"] = t["posicao"].astype("Int64")
    return t.reset_index(drop=True)[
        ["posicao", "nome", "uf", "codigo_ibge", "notificacoes", "confirmados", "graves", "obitos_dengue",
         "hospitalizacoes", "taxa_hospitalizacao", "letalidade", "score_criticidade", "nivel"]
    ]
