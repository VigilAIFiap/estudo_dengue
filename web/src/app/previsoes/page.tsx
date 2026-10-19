"use client";

import { CircleSlash } from "lucide-react";
import { ForecastChart } from "@/components/charts/forecast-chart";
import { GlobalFilters } from "@/components/filters/global-filters";
import { PageHeader } from "@/components/shell/page-header";
import { Panel } from "@/components/ui/panel";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { Schemas } from "@/lib/api";
import { fmtData, fmtDec, fmtInt, fmtMes } from "@/lib/format";
import { usePrevisao } from "@/lib/queries";

export default function PrevisoesPage() {
  const prev = usePrevisao();
  const p = prev.data;

  return (
    <>
      <PageHeader
        titulo="Previsões epidemiológicas"
        descricao="Interface do modelo de séries temporais em src/modelos/series_temporais.py. A tela mostra exatamente o que o modelo devolve: quando ele recusa a série, a recusa e o motivo aparecem aqui."
      />
      <GlobalFilters ignorados={{ periodo: "A previsão usa toda a série histórica do recorte geográfico; o filtro de período não se aplica." }} />

      {prev.isError ? (
        <ErrorState erro={prev.error} tentarNovamente={() => prev.refetch()} />
      ) : !p ? (
        <LoadingState altura={420} />
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          {p.status === "indisponivel" ? <Indisponivel p={p} /> : <Disponivel p={p} />}

          <Panel
            id="serie"
            className="xl:col-span-8"
            titulo={p.status === "disponivel" ? "Série observada e projeção de 12 meses" : "Série mensal observada"}
            subtitulo={`Casos confirmados por mês de notificação até ${fmtData(p.data_referencia)}; o mês em curso é descartado`}
            rodape={
              p.historico[0] &&
              `${fmtMes(p.historico[0].mes)} é o primeiro mês disponível na fonte carregada.`
            }
          >
            <ForecastChart dados={p} />
          </Panel>

          <Panel id="metodo" className="xl:col-span-4" titulo="Metodologia">
            <dl className="flex flex-col gap-3 text-[13px] leading-5">
              {[
                ["Modelo", "SARIMA com sazonalidade anual (m = 12), ordem escolhida por auto_arima (pmdarima)."],
                ["Mínimo exigido", "24 meses completos (duas estações), regra do módulo."],
                ["Horizonte", "12 meses, com intervalo de previsão de 95%."],
                ["Validação", "Janelas móveis: 3 dobras de 3 meses, comparadas ao baseline sazonal ingênuo (repete o mesmo mês do ano anterior)."],
                ["Data de referência", `${fmtData(p.data_referencia)}, última notificação carregada.`],
                [
                  "Definição de caso",
                  "O modelo conta somente CLASSI_FIN 10, 11 e 12: dengue, dengue com sinais de alarme e dengue grave, conforme os confirmados exibidos no restante da plataforma.",
                ],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="font-medium text-ink">{k}</dt>
                  <dd className="text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel id="limites" className="xl:col-span-12" titulo="Limitações">
            <ul className="grid list-disc gap-x-10 gap-y-1.5 pl-5 text-[13px] leading-6 text-ink-2 md:grid-cols-2">
              <li>Uma previsão estatística descreve uma tendência provável, não a certeza de um surto.</li>
              <li>O modelo usa só a própria série de casos: não considera clima, sorotipos circulantes ou ações de controle.</li>
              <li>Notificações recentes ainda podem ser digitadas ou reclassificadas, o que rebaixa os últimos meses observados.</li>
              <li>A base termina em {fmtData(p.data_referencia)}; projeções a partir daí ficam defasadas em relação a hoje.</li>
            </ul>
          </Panel>
        </div>
      )}
    </>
  );
}

function Indisponivel({ p }: { p: Schemas["Previsao"] }) {
  return (
    <section
      aria-labelledby="status-titulo"
      className="flex flex-col gap-3 rounded-panel border border-line bg-surface p-5 xl:col-span-12 sm:flex-row sm:items-start"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-sunken">
        <CircleSlash aria-hidden className="size-5 text-muted" />
      </span>
      <div className="min-w-0">
        <h2 id="status-titulo" className="text-[15px] font-semibold text-ink">
          O modelo não gerou previsão para este recorte
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          Motivo informado pelo modelo: <span className="font-medium text-ink">{p.motivo}</span>
        </p>
        <p className="mt-2 max-w-[80ch] text-[13px] leading-5 text-muted">
          Nenhuma projeção é desenhada para preencher o gráfico. Para destravar, carregue o histórico de anos anteriores (por exemplo,
          DENGBR23 e DENGBR24 do SINAN) ou aguarde novas extrações até completar {fmtInt(24)} meses.
        </p>
      </div>
    </section>
  );
}

function Disponivel({ p }: { p: Schemas["Previsao"] }) {
  const v = p.validacao;
  return (
    <section aria-label="Resultado da previsão" className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line xl:col-span-12 lg:grid-cols-4">
      {[
        ["Próximo mês", p.previsao[0] ? fmtInt(p.previsao[0].previsao) : "—"],
        ["Erro médio do modelo (MAE)", v ? fmtDec(v.model_mae) : "—"],
        ["Erro do baseline sazonal", v ? fmtDec(v.seasonal_naive_mae) : "—"],
        ["Supera o baseline?", v ? (v.beats_seasonal_naive ? "Sim" : "Não") : "—"],
      ].map(([k, val]) => (
        <div key={k} className="bg-surface p-4">
          <p className="text-[13px] text-muted">{k}</p>
          <p className="num mt-1 text-kpi font-semibold text-ink">{val}</p>
        </div>
      ))}
    </section>
  );
}
