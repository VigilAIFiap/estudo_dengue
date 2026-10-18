import { fmtInt, fmtPct } from "@/lib/format";
import { NIVEL, SEM_SCORE, type Nivel } from "@/lib/criticality";
import { CriticalityMeter } from "@/components/ui/criticality-badge";

/** Barras horizontais em HTML: rótulo à esquerda, valor alinhado à direita. */
export function DistributionBars({
  itens,
  cor = "#2563eb",
}: {
  itens: { chave: string | number; rotulo: string; total: number; pct: number; destaque?: boolean }[];
  cor?: string;
}) {
  const max = Math.max(...itens.map((i) => i.total), 1);
  return (
    <ul className="flex flex-col gap-2.5">
      {itens.map((i) => (
        <li key={i.chave} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="truncate text-ink-2">{i.rotulo}</span>
          <span className="num text-right text-ink">
            {fmtInt(i.total)} <span className="ml-1 inline-block w-12 text-muted">{fmtPct(i.pct / 100)}</span>
          </span>
          <span className="col-span-2 h-1.5 rounded-full bg-sunken">
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.max((i.total / max) * 100, i.total ? 0.8 : 0)}%`, background: i.destaque === false ? "#98a3b5" : cor }}
            />
          </span>
        </li>
      ))}
    </ul>
  );
}

export function LevelDistribution({ niveis }: { niveis: { nivel: string; municipios: number; notificacoes: number; obitos: number }[] }) {
  const total = niveis.reduce((s, n) => s + n.municipios, 0) || 1;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex h-3 gap-[2px] overflow-hidden rounded-full" aria-hidden>
        {niveis.map((n) => (
          <span
            key={n.nivel}
            style={{
              width: `${(n.municipios / total) * 100}%`,
              background: n.nivel in NIVEL ? NIVEL[n.nivel as Nivel].fill : SEM_SCORE.fill,
            }}
          />
        ))}
      </div>
      <table className="w-full text-[13px]">
        <caption className="sr-only">Municípios por nível de criticidade</caption>
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="pb-1.5 font-normal">Nível</th>
            <th scope="col" className="pb-1.5 text-right font-normal">Municípios</th>
            <th scope="col" className="pb-1.5 text-right font-normal">Notificações</th>
          </tr>
        </thead>
        <tbody>
          {niveis.map((n) => (
            <tr key={n.nivel} className="border-t border-line">
              <th scope="row" className="py-1.5 text-left font-normal">
                <span className="inline-flex items-center gap-2 text-ink">
                  <CriticalityMeter nivel={n.nivel === "Sem score" ? null : n.nivel} />
                  {n.nivel}
                </span>
              </th>
              <td className="num py-1.5 text-right text-ink">{fmtInt(n.municipios)}</td>
              <td className="num py-1.5 text-right text-muted">{fmtInt(n.notificacoes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
