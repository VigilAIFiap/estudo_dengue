import type { ReactNode } from "react";

export type LinhaTooltip = { cor?: string; tracejado?: boolean; rotulo: string; valor: string };

/** Conteúdo padrão de tooltip: título, linhas com marcador e nota. */
export function ChartTooltipBox({ titulo, linhas, nota }: { titulo: ReactNode; linhas: LinhaTooltip[]; nota?: ReactNode }) {
  return (
    <div className="min-w-48 rounded-control border border-line bg-surface px-3 py-2.5 text-xs shadow-float">
      <p className="mb-1.5 font-medium text-ink">{titulo}</p>
      <ul className="flex flex-col gap-1">
        {linhas.map((l) => (
          <li key={l.rotulo} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted">
              {l.cor && (
                <span
                  aria-hidden
                  className="inline-block h-0.5 w-3"
                  style={{
                    background: l.tracejado ? `repeating-linear-gradient(90deg, ${l.cor} 0 3px, transparent 3px 5px)` : l.cor,
                    height: l.tracejado ? 2 : 8,
                    borderRadius: 2,
                  }}
                />
              )}
              {l.rotulo}
            </span>
            <span className="num font-medium text-ink">{l.valor}</span>
          </li>
        ))}
      </ul>
      {nota && <p className="mt-2 border-t border-line pt-1.5 text-muted">{nota}</p>}
    </div>
  );
}

export function Legenda({ itens }: { itens: { cor: string; rotulo: string; tipo?: "barra" | "linha" | "tracejado" | "hachura" }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      {itens.map((i) => (
        <li key={i.rotulo} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={i.tipo === "hachura" ? "hatch inline-block size-2.5 rounded-[2px] border border-line-strong" : "inline-block"}
            style={
              i.tipo === "linha"
                ? { width: 14, height: 2, background: i.cor, borderRadius: 1 }
                : i.tipo === "tracejado"
                  ? { width: 14, height: 2, background: `repeating-linear-gradient(90deg, ${i.cor} 0 3px, transparent 3px 6px)` }
                  : i.tipo === "hachura"
                    ? undefined
                    : { width: 10, height: 10, background: i.cor, borderRadius: 2 }
            }
          />
          {i.rotulo}
        </li>
      ))}
    </ul>
  );
}
