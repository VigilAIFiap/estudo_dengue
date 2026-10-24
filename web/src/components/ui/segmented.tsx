"use client";

import { cn } from "./cn";

type Opcao<T extends string> = { valor: T; rotulo: string };

export function Segmented<T extends string>({
  opcoes,
  valor,
  onChange,
  rotulo,
}: {
  opcoes: Opcao<T>[];
  valor: T;
  onChange: (v: T) => void;
  rotulo: string;
}) {
  return (
    <div role="radiogroup" aria-label={rotulo} className="inline-flex rounded-control bg-sunken p-0.5">
      {opcoes.map((o) => {
        const ativo = o.valor === valor;
        return (
          <button
            key={o.valor}
            type="button"
            role="radio"
            aria-checked={ativo}
            onClick={() => onChange(o.valor)}
            className={cn(
              "h-7 rounded-[6px] px-2.5 text-xs font-medium whitespace-nowrap transition-colors",
              ativo ? "bg-surface text-ink shadow-[0_1px_2px_rgb(23_32_51/0.08)]" : "text-muted hover:text-ink",
            )}
          >
            {o.rotulo}
          </button>
        );
      })}
    </div>
  );
}
