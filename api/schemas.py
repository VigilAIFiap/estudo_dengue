"""Contratos de resposta da API. O frontend gera seus tipos a partir do OpenAPI."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Nivel = Literal["Crítico", "Alto", "Médio", "Baixo"]


class Opcao(BaseModel):
    codigo: int
    rotulo: str


class UfOpcao(BaseModel):
    sigla: str
    nome: str


class ArquivoFonte(BaseModel):
    nome: str
    bytes: int
    modificado_em: datetime


class Meta(BaseModel):
    fonte_dados: Literal["csv", "oracle"]
    cobertura_inicio: date
    cobertura_fim: date
    padrao_inicio: date
    padrao_fim: date
    defasagem_dias: int
    carregado_em: datetime
    arquivos: list[ArquivoFonte]
    linhas_descartadas: dict[str, int]
    total_notificacoes: int
    ufs: list[UfOpcao]
    classificacoes: list[Opcao]
    confirmados_codigos: list[int]
    niveis: list[Nivel]


class Totais(BaseModel):
    notificacoes: int
    confirmados: int
    graves: int
    obitos: int
    obitos_investigacao: int
    hospitalizacoes: int
    municipios: int


class Variacao(BaseModel):
    notificacoes: float | None
    confirmados: float | None
    graves: float | None
    obitos: float | None
    obitos_investigacao: float | None
    hospitalizacoes: float | None
    municipios: float | None


class Comparacao(BaseModel):
    inicio: date
    fim: date
    totais: Totais
    variacao_pct: Variacao


class Insight(BaseModel):
    id: str
    titulo: str
    detalhe: str
    origem: str
    municipio: int | None


class Alerta(BaseModel):
    id: str
    severidade: Nivel
    titulo: str
    criterio: str


class NivelResumo(BaseModel):
    nivel: str
    municipios: int
    notificacoes: int
    obitos: int


class PontoSerie(BaseModel):
    periodo: str
    inicio: date
    fim: date
    parcial: bool
    notificacoes: int
    confirmados: int
    graves: int
    hospitalizacoes: int
    obitos: int


class Municipio(BaseModel):
    id_municip: int
    nome: str
    uf: str
    capital: bool
    notificacoes: int
    confirmados: int
    graves: int
    obitos_dengue: int
    hospitalizacoes: int
    taxa_hospitalizacao: float | None
    letalidade: float | None
    score: float | None
    nivel: Nivel | None
    posicao: int | None


class Corte(BaseModel):
    nivel: Nivel
    minimo: float | None


class Pesos(BaseModel):
    volume_log: float
    taxa_obito: float
    taxa_hospitalizacao: float


class Metodologia(BaseModel):
    pesos: Pesos
    pseudo_casos_obito: int
    pseudo_casos_hospitalizacao: int
    casos_credibilidade: int
    minimo_casos_critico: int
    q1: float
    cortes: list[Corte]


class VisaoGeral(BaseModel):
    inicio: date
    fim: date
    totais: Totais
    comparacao: Comparacao | None
    motivo_sem_comparacao: str | None
    insights: list[Insight]
    alertas: list[Alerta]
    niveis: list[NivelResumo]
    top_municipios: list[Municipio]
    metodologia: Metodologia


class SemanaAno(BaseModel):
    semana: int
    notificacoes: int
    confirmados: int


class Ano(BaseModel):
    ano: int
    semanas: list[SemanaAno]
    ultima_semana: int
    ultima_semana_parcial: bool


class ComparacaoAnual(BaseModel):
    anos: list[Ano]
    ultima_data: date


class Contagem(BaseModel):
    codigo: int
    rotulo: str
    total: int
    pct: float


class Distribuicoes(BaseModel):
    classificacao: list[Contagem]
    evolucao: list[Contagem]
    hospitalizacao: list[Contagem]


class Ranking(BaseModel):
    total: int
    pagina: int
    tamanho: int
    q1: float
    itens: list[Municipio]
    metodologia: Metodologia


class Componentes(BaseModel):
    volume: float
    obito: float
    hospitalizacao: float
    credibilidade: float
    limitado_por_volume: bool


class DetalheMunicipio(Municipio):
    latitude: float
    longitude: float
    componentes: Componentes | None
    municipios_pontuados: int
    q1: float
    serie: list[PontoSerie]


class MunicipioBusca(BaseModel):
    id_municip: int
    nome: str
    uf: str


class PontoMapa(BaseModel):
    id: int
    nome: str
    uf: str
    lat: float
    lon: float
    notificacoes: int
    confirmados: int
    obitos: int
    hospitalizacoes: int
    score: float | None
    nivel: Nivel | None


class UfMapa(BaseModel):
    uf: str
    nome: str
    notificacoes: int
    confirmados: int
    obitos: int
    hospitalizacoes: int
    municipios: int
    criticos: int


class Mapa(BaseModel):
    pontos: list[PontoMapa]
    ufs: list[UfMapa]
    q1: float


class MesObservado(BaseModel):
    mes: date
    casos: int


class MesPrevisto(BaseModel):
    mes: date
    previsao: int
    inferior: float
    superior: float


class Validacao(BaseModel):
    model_mae: float
    seasonal_naive_mae: float
    model_rmse: float
    seasonal_naive_rmse: float
    beats_seasonal_naive: bool
    test_observations: int


class Previsao(BaseModel):
    status: Literal["disponivel", "indisponivel"]
    motivo: str | None
    data_referencia: date
    historico: list[MesObservado]
    previsao: list[MesPrevisto]
    validacao: Validacao | None


class PatientAssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age_group: Literal["0-4", "5-9", "10-19", "20-39", "40-59", "60+"] | None = None
    sex: Literal["F", "M", "OUTRO"] | None = None
    symptom_duration: Literal["HOJE", "1-3_DIAS", "4+_DIAS"] | None = None
    fever: Literal["SIM", "NAO"] | None = None
    headache: Literal["SIM", "NAO"] | None = None
    muscle_pain: Literal["SIM", "NAO"] | None = None
    rash: Literal["SIM", "NAO"] | None = None
    nausea: Literal["SIM", "NAO"] | None = None
    vomiting: Literal["SIM", "NAO"] | None = None
    pregnancy: Literal["SIM", "NAO"] | None = None
    comorbidities: Literal["SIM", "NAO"] | None = None


class PatientAssessmentCreated(BaseModel):
    intake_id: int
    status: Literal["PENDENTE"]


class Erro(BaseModel):
    detail: str
