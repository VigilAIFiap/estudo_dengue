"use client";

import { DistributionBars } from "@/components/charts/bars";
import { MetricSeries, ROTULO_METRICA, type MetricaSerie } from "@/components/charts/metric-series";
import { GlobalFilters } from "@/components/filters/global-filters";
import { PageHeader } from "@/components/shell/page-header";
import { ExportButton } from "@/components/ui/export-button";
import { Panel } from "@/components/ui/panel";
import { Segmented } from "@/components/ui/segmented";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import type { Schemas } from "@/lib/api";
import { fmtData, fmtInt } from "@/lib/format";
import { urlExportacao, useDistribuicoes, useFiltrosResolvidos, useSeries } from "@/lib/queries";
import { useParametro } from "@/lib/use-filtros";

const METRICAS: MetricaSerie[] = ["notificacoes", "confirmados", "graves", "hospitalizacoes", "obitos"];

export default function HistoricoPage() {
  const { params } = useFiltrosResolvidos();
  const [granParam, setGran] = useParametro("granularidade");
  const [metParam, setMet] = useParametro("metrica");
  const gran = granParam === "mes" ? "mes" : "semana";
  const metrica = (METRICAS.includes(metParam as MetricaSerie) ? metParam : "notificacoes") as MetricaSerie;

  const serie = useSeries(gran);
  const dist = useDistribuicoes();

  return (
    <>
      <PageHeader
        titulo="Análise histórica"
        descricao="Séries por semana epidemiológica ou mês e distribuição das classificações. Arraste a régua sob o gráfico para aproximar um intervalo."
        acoes={<ExportButton href={urlExportacao("/api/export/serie.csv", params, { granularidade: gran })}>Exportar série</ExportButton>}
      />
      <GlobalFilters />

      <div className="grid grid-cols-1 gap-5">
        <Panel
          id="serie"
          titulo={`${ROTULO_METRICA[metrica]} por ${gran === "semana" ? "semana epidemiológica" : "mês"}`}
          subtitulo="Barras hachuradas indicam períodos que o recorte ou os dados não cobrem por inteiro"
          acoes={
            <div className="flex flex-wrap justify-end gap-2">
              <Segmented
                rotulo="Granularidade"
                valor={gran}
                onChange={(v) => setGran(v === "semana" ? null : v)}
                opcoes={[
                  { valor: "semana", rotulo: "Semanal" },
                  { valor: "mes", rotulo: "Mensal" },
                ]}
              />
            </div>
          }
        >
          <div className="mb-3 overflow-x-auto">
            <Segmented
              rotulo="Indicador"
              valor={metrica}
              onChange={(v) => setMet(v === "notificacoes" ? null : v)}
              opcoes={METRICAS.map((m) => ({ valor: m, rotulo: ROTULO_METRICA[m] }))}
            />
          </div>
          {serie.isError ? (
            <ErrorState erro={serie.error} tentarNovamente={() => serie.refetch()} />
          ) : !serie.data ? (
            <LoadingState altura={340} />
          ) : !serie.data.length ? (
            <EmptyState titulo="Nenhuma notificação no recorte">Ajuste os filtros para ver a série.</EmptyState>
          ) : (
            <MetricSeries serie={serie.data} metrica={metrica} altura={340} />
          )}
        </Panel>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Panel id="classificacao" titulo="Classificação final" subtitulo="Códigos da ficha de notificação SINAN">
            {!dist.data ? <LoadingState altura={220} /> : <Distribuicao itens={dist.data.classificacao} confirmados={[10, 11, 12]} />}
          </Panel>
          <Panel id="evolucao" titulo="Evolução do caso" subtitulo="Desfecho registrado na notificação">
            {!dist.data ? <LoadingState altura={220} /> : <Distribuicao itens={dist.data.evolucao} />}
          </Panel>
          <Panel id="hospitalizacao" titulo="Hospitalização" subtitulo="Campo HOSPITALIZ, incluindo não preenchidos">
            {!dist.data ? <LoadingState altura={220} /> : <Distribuicao itens={dist.data.hospitalizacao} />}
          </Panel>
        </div>

        <Panel id="tabela" titulo="Tabela detalhada" subtitulo={`Valores da série ${gran === "semana" ? "semanal" : "mensal"} exibida acima`}>
          {!serie.data ? <LoadingState altura={240} /> : <TabelaSerie serie={serie.data} />}
        </Panel>
      </div>
    </>
  );
}

function Distribuicao({ itens, confirmados }: { itens: Schemas["Contagem"][]; confirmados?: number[] }) {
  if (!itens.length) return <EmptyState titulo="Sem notificações no recorte" />;
  return (
    <DistributionBars
      itens={itens.map((i) => ({
        chave: i.codigo,
        rotulo: i.codigo >= 0 && i.codigo !== 0 ? `${i.rotulo} (${i.codigo})` : i.rotulo,
        total: i.total,
        pct: i.pct,
        destaque: confirmados ? confirmados.includes(i.codigo) : true,
      }))}
    />
  );
}

function TabelaSerie({ serie }: { serie: Schemas["PontoSerie"][] }) {
  if (!serie.length) return <EmptyState titulo="Sem dados" />;
  const colunas = ["notificacoes", "confirmados", "graves", "hospitalizacoes", "obitos"] as const;
  return (
    <div className="max-h-[420px] overflow-auto rounded-control border border-line">
      <table className="w-full min-w-[720px] text-[13px]">
        <caption className="sr-only">Série temporal detalhada</caption>
        <thead className="sticky top-0 bg-canvas text-xs text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium">Período</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Datas</th>
            {colunas.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 text-right font-medium">
                {ROTULO_METRICA[c]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {serie.map((p) => (
            <tr key={p.inicio} className="border-t border-line">
              <th scope="row" className="px-3 py-1.5 text-left font-normal text-ink">
                {p.periodo}
                {p.parcial && <span className="ml-2 rounded bg-sunken px-1.5 py-0.5 text-2xs text-muted">parcial</span>}
              </th>
              <td className="num px-3 py-1.5 text-muted">
                {fmtData(p.inicio)} a {fmtData(p.fim)}
              </td>
              {colunas.map((c) => (
                <td key={c} className="num px-3 py-1.5 text-right text-ink">
                  {fmtInt(p[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
