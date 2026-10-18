import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";
import { fmtVariacao } from "@/lib/format";
import { InfoTip } from "./info-tip";
import { Skeleton } from "./states";

export type Metrica = {
  id: string;
  rotulo: string;
  valor: string;
  unidade?: string;
  variacao?: number | null;
  /** Para óbitos e hospitalizações, aumento é ruim; para nenhum indicador aqui aumento é "bom". */
  comparacaoRotulo?: string;
  detalhe?: ReactNode;
  calculo: ReactNode;
};

/** Faixa única de indicadores, separados por divisórias — não cartões soltos. */
export function MetricBand({ metricas, carregando }: { metricas: Metrica[]; carregando?: boolean }) {
  return (
    <section
      aria-label="Indicadores principais"
      className="grid grid-cols-2 overflow-hidden rounded-panel border border-line bg-surface sm:grid-cols-3 xl:grid-cols-6"
    >
      {metricas.map((m) => (
        <div
          key={m.id}
          className="relative flex min-w-0 flex-col gap-1 border-line px-4 py-4 not-last:border-b sm:border-r sm:[&:nth-child(3n)]:border-r-0 xl:border-b-0 xl:[&:nth-child(3n)]:border-r xl:last:border-r-0"
        >
          <div className="flex items-start gap-1">
            <h3 className="line-clamp-2 text-[13px] leading-5 text-muted">{m.rotulo}</h3>
            <InfoTip rotulo={`Como é calculado: ${m.rotulo}`}>{m.calculo}</InfoTip>
          </div>
          {carregando ? (
            <Skeleton className="h-8 w-24" />
          ) : (
            <p className="num text-kpi font-semibold text-ink">
              {m.valor}
              {m.unidade && <span className="ml-1 text-sm font-normal text-muted">{m.unidade}</span>}
            </p>
          )}
          <div className="min-h-5 text-xs leading-5 text-muted">
            {!carregando && m.comparacaoRotulo !== undefined && <Variacao pct={m.variacao} rotulo={m.comparacaoRotulo} />}
            {!carregando && m.detalhe}
          </div>
        </div>
      ))}
    </section>
  );
}

function Variacao({ pct, rotulo }: { pct: number | null | undefined; rotulo: string }) {
  if (pct == null) return <span>{rotulo}</span>;
  const Icone = pct > 0 ? ArrowUpRight : pct < 0 ? ArrowDownRight : Minus;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1">
      <span className="num inline-flex items-center gap-0.5 font-medium text-ink-2">
        <Icone aria-hidden className="size-3.5" />
        {fmtVariacao(pct)}
      </span>
      <span>{rotulo}</span>
    </span>
  );
}
