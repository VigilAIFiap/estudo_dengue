"use client";

import { cn } from "@/components/ui/cn";
import type { CampoTriagem } from "@/lib/triagem";

export type Opcao = { valor: string; rotulo: string };

type Props = {
  campo: CampoTriagem;
  legenda: string;
  opcoes: Opcao[];
  valor: string;
  aoMudar: (campo: CampoTriagem, valor: string) => void;
  dica?: string;
};

/** Escolha única em botões; a legenda é o nome acessível do grupo. */
export function ChoiceGroup({ campo, legenda, opcoes, valor, aoMudar, dica }: Props) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-[13px] font-medium text-ink">{legenda}</legend>
      <div className="flex flex-wrap gap-1.5">
        {opcoes.map((o) => (
          <label key={o.valor || "vazio"} className="cursor-pointer">
            <input
              type="radio"
              className="peer sr-only"
              name={campo}
              value={o.valor}
              checked={valor === o.valor}
              onChange={() => aoMudar(campo, o.valor)}
            />
            <span
              className={cn(
                "inline-flex h-9 items-center rounded-control border px-3 text-[13px] transition-colors",
                "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary",
                o.valor === ""
                  ? "border-line bg-surface text-muted hover:border-line-strong peer-checked:border-line-strong peer-checked:bg-sunken peer-checked:text-ink-2"
                  : "border-line bg-surface text-ink-2 hover:border-primary/50 hover:bg-primary-soft peer-checked:border-primary peer-checked:bg-primary peer-checked:font-medium peer-checked:text-white",
              )}
            >
              {o.rotulo}
            </span>
          </label>
        ))}
      </div>
      {dica && <p className="mt-1.5 text-xs leading-4 text-muted">{dica}</p>}
    </fieldset>
  );
}
