"""Vigil Assist: assistente que responde somente a partir das consultas da API.

Requer ANTHROPIC_API_KEY. Sem a chave, a rota responde 503 e a interface
informa a limitação — não há respostas simuladas.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable

from . import analytics as a
from .dataset import Dataset

MAX_RODADAS = 6

SISTEMA = """Você é o Vigil Assist, assistente de análise epidemiológica de dengue para gestores públicos.
Regras:
- Responda em português do Brasil, de forma objetiva.
- Use SOMENTE números obtidos pelas ferramentas nesta conversa. Se a ferramenta não cobre a pergunta, diga que não há dado disponível.
- Sempre informe o período e o recorte geográfico dos números.
- Diferencie notificações, casos confirmados (CLASSI_FIN 10, 11 e 12), óbitos pelo agravo e hospitalizações.
- O score de criticidade é um indicador analítico relativo do projeto, não um protocolo oficial de risco.
- Não faça afirmações causais, diagnósticos ou recomendações clínicas.
- Os dados podem ter atraso de notificação e revisões; a cobertura vai de {inicio} a {fim}."""

_PROPRIEDADES_FILTRO = {
    "inicio": {"type": "string", "description": "Data inicial AAAA-MM-DD"},
    "fim": {"type": "string", "description": "Data final AAAA-MM-DD"},
    "ufs": {"type": "array", "items": {"type": "string"}, "description": "Siglas de UF, ex.: ['SP']"},
}

FERRAMENTAS = [
    {
        "name": "visao_geral",
        "description": "Totais do recorte (notificações, confirmados, graves, óbitos, hospitalizações, municípios), comparação com as mesmas semanas do ano anterior, insights e alertas.",
        "input_schema": {"type": "object", "properties": _PROPRIEDADES_FILTRO},
    },
    {
        "name": "ranking_municipios",
        "description": "Municípios ordenados por score de criticidade ou por outra métrica.",
        "input_schema": {
            "type": "object",
            "properties": {
                **_PROPRIEDADES_FILTRO,
                "ordenar": {"type": "string", "enum": sorted(a.COLUNAS_ORDENAVEIS)},
                "limite": {"type": "integer", "minimum": 1, "maximum": 30},
            },
        },
    },
    {
        "name": "serie_temporal",
        "description": "Série semanal (semana epidemiológica) ou mensal do recorte.",
        "input_schema": {
            "type": "object",
            "properties": {**_PROPRIEDADES_FILTRO, "granularidade": {"type": "string", "enum": ["semana", "mes"]}},
            "required": ["granularidade"],
        },
    },
    {
        "name": "municipio",
        "description": "Indicadores e score de um município, buscado pelo nome.",
        "input_schema": {
            "type": "object",
            "properties": {**_PROPRIEDADES_FILTRO, "nome": {"type": "string"}},
            "required": ["nome"],
        },
    },
]


def _filtros(entrada: dict[str, Any]) -> a.Filtros:
    ufs = tuple(u.upper() for u in entrada.get("ufs") or ())
    return a.Filtros(
        inicio=date.fromisoformat(entrada["inicio"]) if entrada.get("inicio") else None,
        fim=date.fromisoformat(entrada["fim"]) if entrada.get("fim") else None,
        ufs=ufs,
    )


def executar_ferramenta(ds: Dataset, nome: str, entrada: dict[str, Any]) -> Any:
    f = _filtros(entrada)
    if nome == "visao_geral":
        return {**a.visao_geral(ds, f), **a.insights_e_alertas(ds, f)}
    if nome == "ranking_municipios":
        return a.ranking(
            ds, f, pagina=1, tamanho=int(entrada.get("limite", 10)),
            ordenar=entrada.get("ordenar", "score_criticidade"), direcao="desc", busca=None, niveis=(),
        )
    if nome == "serie_temporal":
        return a.serie(ds, f, entrada["granularidade"])
    if nome == "municipio":
        achados = a.buscar_municipios(ds, entrada["nome"], limite=1)
        if not achados:
            return {"erro": f"Nenhum município com notificações encontrado para '{entrada['nome']}'."}
        detalhe = a.detalhe_municipio(ds, f, achados[0]["id_municip"])
        detalhe.pop("serie")
        return detalhe
    raise ValueError(f"Ferramenta desconhecida: {nome}")


def responder(
    ds: Dataset,
    mensagens: list[dict[str, str]],
    criar_mensagem: Callable[..., Any],
    modelo: str,
) -> dict[str, Any]:
    """Laço de uso de ferramentas. `criar_mensagem` é client.messages.create."""
    inicio, fim = a.cobertura(ds)
    historico: list[dict[str, Any]] = [
        {"role": "user" if m["papel"] == "usuario" else "assistant", "content": m["texto"]} for m in mensagens
    ]
    consultas: list[dict[str, Any]] = []
    for _ in range(MAX_RODADAS):
        resposta = criar_mensagem(
            model=modelo,
            max_tokens=1500,
            system=SISTEMA.format(inicio=inicio.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y")),
            tools=FERRAMENTAS,
            messages=historico,
        )
        if resposta.stop_reason != "tool_use":
            texto = "".join(b.text for b in resposta.content if b.type == "text")
            return {"texto": texto, "consultas": consultas}
        historico.append({"role": "assistant", "content": resposta.content})
        resultados = []
        for bloco in resposta.content:
            if bloco.type != "tool_use":
                continue
            consultas.append({"ferramenta": bloco.name, "parametros": bloco.input})
            try:
                conteudo = json.dumps(executar_ferramenta(ds, bloco.name, bloco.input), default=str, ensure_ascii=False)
                erro = False
            except (ValueError, KeyError, LookupError) as e:
                conteudo, erro = str(e), True
            resultados.append(
                {"type": "tool_result", "tool_use_id": bloco.id, "content": conteudo, "is_error": erro}
            )
        historico.append({"role": "user", "content": resultados})
    raise RuntimeError("O assistente excedeu o limite de consultas sem concluir a resposta.")
