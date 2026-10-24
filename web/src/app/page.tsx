"use client";

import Link from "next/link";
import { GlobalFilters } from "@/components/filters/global-filters";
import { EpiCurve } from "@/components/charts/epi-curve";
import { LevelDistribution } from "@/components/charts/bars";
import { PageHeader } from "@/components/shell/page-header";
import { useHrefComFiltros } from "@/components/shell/app-sidebar";
import { AlertList } from "@/components/ui/alert-list";
import { ExportButton } from "@/components/ui/export-button";
import { InfoTip } from "@/components/ui/info-tip";
import { InsightCard } from "@/components/ui/insight-card";
import { MetricBand, type Metrica } from "@/components/ui/metric-band";
import { Panel } from "@/components/ui/panel";
import { RankingList } from "@/components/ui/ranking-list";
import { ResultadoDestaque } from "@/components/ui/resultado-destaque";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import type { Schemas } from "@/lib/api";
import { fmtData, fmtInt, fmtPct } from "@/lib/format";
import { useRotuloBase } from "@/lib/base-municipal";
import { urlExportacao, useFiltrosResolvidos, useSeries, useSeriesEm, useVisaoGeral } from "@/lib/queries";

export default function VisaoGeralPage() {
  const { params } = useFiltrosResolvidos();
  const rotuloBase = useRotuloBase();
  const visao = useVisaoGeral();
  const serie = useSeries("semana");
  const comparacao = visao.data?.comparacao;
  const anterior = useSeriesEm("semana", comparacao ? { inicio: comparacao.inicio, fim: comparacao.fim } : null);
  const href = useHrefComFiltros();
  const v = visao.data;

  return (
    <>
      <PageHeader
        titulo="Visão geral epidemiológica"
        descricao={`Notificações de dengue no SINAN por ${rotuloBase}. Os indicadores, a curva e o ranking seguem os mesmos filtros.`}
        acoes={<ExportButton href={urlExportacao("/api/export/agregado.csv", params)}>Exportar mês × município</ExportButton>}
      />
      <GlobalFilters />

      {v && <ResultadoDestaque visao={v} hrefMapa={href("/mapa")} />}

      {visao.isError ? (
        <ErrorState erro={visao.error} tentarNovamente={() => visao.refetch()} />
      ) : (
        <MetricBand carregando={!v} metricas={v ? metricas(v) : metricasVazias} />
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Panel
          id="curva"
          destaque="primary"
          className="xl:col-span-8"
          titulo="Curva epidêmica por semana epidemiológica"
          subtitulo={
            v
              ? `${fmtData(v.inicio)} a ${fmtData(v.fim)}${comparacao ? `, com as mesmas semanas de ${comparacao.inicio.slice(0, 4)}` : ""}`
              : "Carregando período"
          }
          rodape="Data de notificação (DT_NOTIFIC). As últimas semanas costumam subir em extrações futuras por atraso de digitação."
        >
          {serie.isError ? (
            <ErrorState erro={serie.error} tentarNovamente={() => serie.refetch()} />
          ) : !serie.data ? (
            <LoadingState altura={300} />
          ) : serie.data.length === 0 ? (
            <EmptyState titulo="Nenhuma notificação no recorte">Ajuste o período, a UF ou a classificação.</EmptyState>
          ) : (
            <EpiCurve serie={serie.data} anterior={comparacao ? anterior.data : undefined} />
          )}
        </Panel>

        <Panel
          id="alertas"
          destaque="alto"
          className="xl:col-span-4"
          titulo="Alertas analíticos"
          subtitulo="Disparados por critérios fixos, descritos em cada item"
        >
          {!v ? <LoadingState altura={220} /> : <AlertList alertas={v.alertas} />}
        </Panel>

        <Panel
          id="ranking"
          destaque="critico"
          className="xl:col-span-6"
          titulo="Municípios mais críticos"
          subtitulo="Top 10 pelo score de criticidade do projeto"
          acoes={
            <Link href={href("/municipios")} className="text-[13px] font-medium text-primary-ink hover:underline">
              Ver ranking completo
            </Link>
          }
          rodape={
            v && (
              <span className="inline-flex items-center gap-1">
                Score relativo aos municípios do recorte; não é protocolo oficial de risco.
                <InfoTip>
                  Score = fator de volume (log das notificações, de 0 a 1) × severidade ({Math.round(v.metodologia.pesos.taxa_obito * 100)}%
                  taxa de óbito e {Math.round(v.metodologia.pesos.taxa_hospitalizacao * 100)}% taxa de hospitalização, em percentil entre os
                  municípios). Considera os municípios com mais notificações que o 1º quartil ({fmtInt(v.metodologia.q1)}). As taxas de
                  municípios com poucos casos são suavizadas em direção à média (peso de {v.metodologia.suavizacao_casos} casos). Cortes: Crítico ≥
                  50, Alto ≥ 35, Médio ≥ 20.
                </InfoTip>
              </span>
            )
          }
        >
          {!v ? <LoadingState altura={360} /> : <RankingList itens={v.top_municipios} />}
        </Panel>

        <Panel
          id="niveis"
          destaque="teal"
          className="xl:col-span-6"
          titulo="Municípios por nível de criticidade"
          subtitulo="Quantos municípios do recorte estão em cada faixa do score"
          acoes={
            <Link href={href("/mapa")} className="text-[13px] font-medium text-primary-ink hover:underline">
              Abrir mapa
            </Link>
          }
        >
          {!v ? <LoadingState altura={360} /> : <LevelDistribution niveis={v.niveis} />}
        </Panel>
      </div>

      <section aria-labelledby="insights-titulo" className="mt-5">
        <h2 id="insights-titulo" className="mb-3 text-[15px] font-semibold text-ink">
          Leituras do recorte
        </h2>
        {!v ? (
          <LoadingState altura={140} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {v.insights.map((i) => (
              <InsightCard key={i.id} insight={i} />
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-muted">
          Descrições calculadas a partir das notificações. Concentração ou variação não indica causa.
        </p>
      </section>
    </>
  );
}

const anteriorRotulo = (v: Schemas["VisaoGeral"]) =>
  v.comparacao ? `vs. mesmo período de ${v.comparacao.inicio.slice(0, 4)}` : "sem período comparável";

function metricas(v: Schemas["VisaoGeral"]): Metrica[] {
  const t = v.totais;
  const vp = v.comparacao?.variacao_pct;
  const rotulo = anteriorRotulo(v);
  return [
    {
      id: "notificacoes",
      tom: "primary",
      rotulo: "Notificações",
      valor: fmtInt(t.notificacoes),
      variacao: vp?.notificacoes,
      comparacaoRotulo: rotulo,
      calculo: (
        <>
          Todos os registros de notificação no período, independentemente da classificação final.
          {v.comparacao && <> Comparação com {fmtData(v.comparacao.inicio)} a {fmtData(v.comparacao.fim)} (mesmas semanas epidemiológicas).</>}
        </>
      ),
    },
    {
      id: "confirmados",
      tom: "teal",
      rotulo: "Casos confirmados",
      valor: fmtInt(t.confirmados),
      variacao: vp?.confirmados,
      comparacaoRotulo: rotulo,
      calculo:
        "Classificação final 10 (dengue), 11 (com sinais de alarme) ou 12 (grave), conforme a ficha SINAN. Casos ainda sem classificação não entram.",
    },
    {
      id: "graves",
      tom: "alto",
      rotulo: "Alarme ou grave",
      valor: fmtInt(t.graves),
      variacao: vp?.graves,
      comparacaoRotulo: rotulo,
      calculo: "Classificação final 11 (dengue com sinais de alarme) ou 12 (dengue grave).",
    },
    {
      id: "obitos",
      tom: "critico",
      rotulo: "Óbitos pelo agravo",
      valor: fmtInt(t.obitos),
      variacao: vp?.obitos,
      comparacaoRotulo: rotulo,
      detalhe: t.obitos_investigacao ? <span className="block">{fmtInt(t.obitos_investigacao)} em investigação</span> : null,
      calculo:
        "Evolução do caso = 2 (óbito pelo agravo), mesma regra da camada Ouro. Óbitos por outras causas (3) e em investigação (4) não entram.",
    },
    {
      id: "hospitalizacoes",
      tom: "medio",
      rotulo: "Hospitalizações",
      valor: fmtInt(t.hospitalizacoes),
      variacao: vp?.hospitalizacoes,
      comparacaoRotulo: rotulo,
      detalhe: <span className="block">{fmtPct(t.notificacoes ? t.hospitalizacoes / t.notificacoes : null)} das notificações</span>,
      calculo: "Campo HOSPITALIZ = 1 (sim). Registros com campo vazio ou ignorado não são contados.",
    },
  ];
}

const metricasVazias: Metrica[] = ["Notificações", "Casos confirmados", "Alarme ou grave", "Óbitos pelo agravo", "Hospitalizações"].map(
  (rotulo) => ({ id: rotulo, rotulo, valor: "", calculo: "" }),
);
