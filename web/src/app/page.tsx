"use client";

import Link from "next/link";
import { GlobalFilters } from "@/components/filters/global-filters";
import { EpiCurve } from "@/components/charts/epi-curve";
import { DistributionBars, LevelDistribution } from "@/components/charts/bars";
import { PageHeader } from "@/components/shell/page-header";
import { useHrefComFiltros } from "@/components/shell/app-sidebar";
import { AlertList } from "@/components/ui/alert-list";
import { ExportButton } from "@/components/ui/export-button";
import { InfoTip } from "@/components/ui/info-tip";
import { InsightCard } from "@/components/ui/insight-card";
import { MetricBand, type Metrica } from "@/components/ui/metric-band";
import { Panel } from "@/components/ui/panel";
import { RankingList } from "@/components/ui/ranking-list";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import type { Schemas } from "@/lib/api";
import { fmtData, fmtInt, fmtPct } from "@/lib/format";
import { urlExportacao, useFiltrosResolvidos, useMapa, useSeries, useSeriesEm, useVisaoGeral } from "@/lib/queries";

export default function VisaoGeralPage() {
  const { params } = useFiltrosResolvidos();
  const visao = useVisaoGeral();
  const serie = useSeries("semana");
  const comparacao = visao.data?.comparacao;
  const anterior = useSeriesEm("semana", comparacao ? { inicio: comparacao.inicio, fim: comparacao.fim } : null);
  const mapa = useMapa();
  const href = useHrefComFiltros();
  const v = visao.data;

  return (
    <>
      <PageHeader
        titulo="Visão geral epidemiológica"
        descricao="Notificações de dengue no SINAN por município notificador. Os indicadores, a curva e o ranking seguem os mesmos filtros."
        acoes={<ExportButton href={urlExportacao("/api/export/agregado.csv", params)}>Exportar mês × município</ExportButton>}
      />
      <GlobalFilters />

      {visao.isError ? (
        <ErrorState erro={visao.error} tentarNovamente={() => visao.refetch()} />
      ) : (
        <MetricBand carregando={!v} metricas={v ? metricas(v) : metricasVazias} />
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Panel
          id="curva"
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
          className="xl:col-span-4"
          titulo="Alertas analíticos"
          subtitulo="Disparados por critérios fixos, descritos em cada item"
        >
          {!v ? <LoadingState altura={220} /> : <AlertList alertas={v.alertas} />}
        </Panel>

        <Panel
          id="ranking"
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
                  50% volume de notificações (log), 30% taxa de óbito, 20% taxa de hospitalização, normalizados entre os
                  municípios com volume acima do 1º quartil ({fmtInt(v.metodologia.q1)} notificações). As taxas são suavizadas e
                  pesam menos em municípios com poucos casos. Cortes: Crítico ≥ 50 (e ao menos{" "}
                  {fmtInt(v.metodologia.minimo_casos_critico)} notificações), Alto ≥ 35, Médio ≥ 20.
                </InfoTip>
              </span>
            )
          }
        >
          {!v ? <LoadingState altura={360} /> : <RankingList itens={v.top_municipios} />}
        </Panel>

        <div className="flex flex-col gap-5 xl:col-span-6">
        <Panel id="niveis" titulo="Municípios por nível de criticidade" subtitulo="Quantos municípios do recorte estão em cada faixa do score">
          {!v ? <LoadingState altura={200} /> : <LevelDistribution niveis={v.niveis} />}
        </Panel>

        <Panel
          id="ufs"
          className="flex-1"
          titulo="Distribuição geográfica"
          subtitulo="UFs com mais notificações no recorte"
          acoes={
            <Link href={href("/mapa")} className="text-[13px] font-medium text-primary-ink hover:underline">
              Abrir mapa
            </Link>
          }
        >
          {!mapa.data ? <LoadingState altura={300} /> : <UfBars ufs={mapa.data.ufs} />}
        </Panel>
        </div>
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

function UfBars({ ufs }: { ufs: Schemas["UfMapa"][] }) {
  const total = ufs.reduce((s, u) => s + u.notificacoes, 0);
  const topo = [...ufs].sort((a, b) => b.notificacoes - a.notificacoes).slice(0, 6);
  if (!total) return <EmptyState titulo="Sem notificações no recorte" />;
  return (
    <DistributionBars
      itens={topo.map((u) => ({ chave: u.uf, rotulo: u.nome, total: u.notificacoes, pct: (u.notificacoes / total) * 100 }))}
    />
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
      rotulo: "Casos confirmados",
      valor: fmtInt(t.confirmados),
      variacao: vp?.confirmados,
      comparacaoRotulo: rotulo,
      calculo:
        "Classificação final 10 (dengue), 11 (com sinais de alarme) ou 12 (grave), conforme a ficha SINAN. Casos ainda sem classificação não entram.",
    },
    {
      id: "graves",
      rotulo: "Alarme ou grave",
      valor: fmtInt(t.graves),
      variacao: vp?.graves,
      comparacaoRotulo: rotulo,
      calculo: "Classificação final 11 (dengue com sinais de alarme) ou 12 (dengue grave).",
    },
    {
      id: "obitos",
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
      rotulo: "Hospitalizações",
      valor: fmtInt(t.hospitalizacoes),
      variacao: vp?.hospitalizacoes,
      comparacaoRotulo: rotulo,
      detalhe: <span className="block">{fmtPct(t.notificacoes ? t.hospitalizacoes / t.notificacoes : null)} das notificações</span>,
      calculo: "Campo HOSPITALIZ = 1 (sim). Registros com campo vazio ou ignorado não são contados.",
    },
    {
      id: "municipios",
      rotulo: "Municípios notificantes",
      valor: fmtInt(t.municipios),
      variacao: vp?.municipios,
      comparacaoRotulo: rotulo,
      calculo: "Municípios notificadores distintos (ID_MUNICIP) com ao menos uma notificação no recorte.",
    },
  ];
}

const metricasVazias: Metrica[] = ["Notificações", "Casos confirmados", "Alarme ou grave", "Óbitos pelo agravo", "Hospitalizações", "Municípios notificantes"].map(
  (rotulo) => ({ id: rotulo, rotulo, valor: "", calculo: "" }),
);
