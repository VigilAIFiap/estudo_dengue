"use client";

import { X } from "lucide-react";
import { MetricSeries } from "@/components/charts/metric-series";
import { CriticalityBadge } from "@/components/ui/criticality-badge";
import { Panel } from "@/components/ui/panel";
import { LoadingState } from "@/components/ui/states";
import { fmtDec, fmtInt, fmtPct } from "@/lib/format";
import { useMunicipio } from "@/lib/queries";
import { Button } from "@/components/ui/button";

/** Comparação lado a lado: tabela e pequenos múltiplos na mesma escala de cada município. */
export function Comparison({ ids, onRemover, onLimpar }: { ids: number[]; onRemover: (id: number) => void; onLimpar: () => void }) {
  return (
    <Panel
      id="comparacao"
      titulo="Comparação entre municípios"
      subtitulo="Indicadores no mesmo recorte. Cada gráfico tem escala própria: compare formas, não alturas."
      acoes={<Button variante="fantasma" onClick={onLimpar}>Limpar comparação</Button>}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {ids.map((id) => (
          <Coluna key={id} id={id} onRemover={() => onRemover(id)} />
        ))}
      </div>
    </Panel>
  );
}

function Coluna({ id, onRemover }: { id: number; onRemover: () => void }) {
  const { data: m } = useMunicipio(id);
  if (!m) return <LoadingState altura={320} />;
  const linhas: [string, string][] = [
    ["Notificações", fmtInt(m.notificacoes)],
    ["Confirmados", fmtInt(m.confirmados)],
    ["Alarme ou grave", fmtInt(m.graves)],
    ["Óbitos pelo agravo", fmtInt(m.obitos_dengue)],
    ["Hospitalizações", fmtInt(m.hospitalizacoes)],
    ["Taxa de hospitalização", fmtPct(m.taxa_hospitalizacao)],
    ["Letalidade", fmtPct(m.letalidade, 2)],
    ["Score", m.score == null ? "—" : fmtDec(m.score)],
  ];
  return (
    <article className="flex flex-col gap-3 rounded-control border border-line p-3">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">{m.nome}</h3>
          <p className="text-xs text-muted">{m.uf}</p>
        </div>
        <button type="button" aria-label={`Remover ${m.nome} da comparação`} onClick={onRemover} className="rounded p-1 text-muted hover:bg-sunken">
          <X aria-hidden className="size-4" />
        </button>
      </header>
      <CriticalityBadge nivel={m.nivel} />
      <dl className="flex flex-col text-[13px]">
        {linhas.map(([k, v]) => (
          <div key={k} className="flex justify-between border-t border-line py-1">
            <dt className="text-muted">{k}</dt>
            <dd className="num text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <MetricSeries serie={m.serie} metrica="notificacoes" altura={120} />
    </article>
  );
}
