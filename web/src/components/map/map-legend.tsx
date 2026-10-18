import { NIVEL, NIVEIS, SEM_SCORE } from "@/lib/criticality";
import { fmtInt } from "@/lib/format";
import { CriticalityMeter } from "@/components/ui/criticality-badge";
import { RAMPA, ROTULO_CAMADA, SEM_NOTIFICACAO, type Camada } from "./brazil-map";

export function MapLegend({ camada, cortes }: { camada: Camada; cortes: number[] }) {
  if (camada === "score") {
    return (
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-2" aria-label="Legenda: nível de criticidade">
        {NIVEIS.map((n) => (
          <li key={n} className="flex items-center gap-1.5">
            <span aria-hidden className="size-3 rounded-[3px]" style={{ background: NIVEL[n].fill }} />
            <CriticalityMeter nivel={n} />
            {n} <span className="text-muted">({NIVEL[n].descricao.toLowerCase()})</span>
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-[3px]" style={{ background: SEM_SCORE.fill }} />
          Sem score
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-[3px] border border-line" style={{ background: SEM_NOTIFICACAO }} />
          Sem notificação
        </li>
      </ul>
    );
  }
  const limites = [0, ...cortes];
  return (
    <div className="flex flex-col gap-1.5" aria-label={`Legenda: ${ROTULO_CAMADA[camada]}`}>
      <div className="flex items-stretch gap-[2px]">
        <span className="h-2.5 w-8 rounded-l-[3px] border border-line" style={{ background: SEM_NOTIFICACAO }} title="Zero" />
        {RAMPA.slice(0, limites.length).map((c, i) => (
          <span key={c} className="h-2.5 flex-1 last:rounded-r-[3px]" style={{ background: c, minWidth: 28 }} title={faixa(limites, i)} />
        ))}
      </div>
      <div className="flex gap-[2px] text-2xs text-muted">
        <span className="w-8">0</span>
        {limites.map((_, i) => (
          <span key={i} className="num flex-1 truncate" style={{ minWidth: 28 }}>
            {faixa(limites, i)}
          </span>
        ))}
      </div>
      <p className="text-2xs text-muted">Classes por quantis entre os municípios com ao menos um registro.</p>
    </div>
  );
}

function faixa(limites: number[], i: number) {
  const de = Math.floor(limites[i]!) + 1;
  const ate = limites[i + 1];
  return ate == null ? `${fmtInt(de)}+` : de >= Math.floor(ate) ? fmtInt(Math.floor(ate)) : `${fmtInt(de)}–${fmtInt(Math.floor(ate))}`;
}
