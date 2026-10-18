"use client";

import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "./cn";

export type OpcaoMulti<T extends string | number> = { valor: T; rotulo: string; detalhe?: string };

/** Seleção múltipla com busca, operável por teclado (lista de checkboxes nativos). */
export function MultiSelect<T extends string | number>({
  rotulo,
  opcoes,
  selecionados,
  onChange,
  resumo,
  buscavel = false,
  largura = 280,
}: {
  rotulo: string;
  opcoes: OpcaoMulti<T>[];
  selecionados: T[];
  onChange: (v: T[]) => void;
  resumo: string;
  buscavel?: boolean;
  largura?: number;
}) {
  const [termo, setTermo] = useState("");
  const visiveis = useMemo(() => {
    const t = termo.trim().toLowerCase();
    return t ? opcoes.filter((o) => `${o.rotulo} ${o.valor}`.toLowerCase().includes(t)) : opcoes;
  }, [opcoes, termo]);
  const ativo = selecionados.length > 0;

  return (
    <Popover.Root onOpenChange={(aberto) => !aberto && setTermo("")}>
      <Popover.Trigger asChild>
        <button type="button" className={gatilho(ativo)}>
          <span className="text-muted">{rotulo}</span>
          <span className="max-w-40 truncate font-medium text-ink">{resumo}</span>
          <ChevronDown aria-hidden className="size-3.5 text-faint" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          style={{ width: largura }}
          className="z-50 rounded-control border border-line bg-surface p-1 shadow-float"
        >
          {buscavel && (
            <label className="mb-1 flex items-center gap-2 border-b border-line px-2 pb-1.5 pt-1">
              <Search aria-hidden className="size-3.5 text-faint" />
              <span className="sr-only">Buscar em {rotulo}</span>
              <input
                autoFocus
                value={termo}
                onChange={(e) => setTermo(e.target.value)}
                placeholder="Buscar"
                className="h-7 w-full bg-transparent text-sm outline-none placeholder:text-faint"
              />
            </label>
          )}
          <fieldset className="max-h-72 overflow-y-auto">
            <legend className="sr-only">{rotulo}</legend>
            {visiveis.map((o) => {
              const marcado = selecionados.includes(o.valor);
              return (
                <label
                  key={String(o.valor)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-canvas has-focus-visible:bg-canvas"
                >
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={marcado}
                    onChange={() =>
                      onChange(marcado ? selecionados.filter((s) => s !== o.valor) : [...selecionados, o.valor])
                    }
                  />
                  <span
                    aria-hidden
                    className={cn(
                      "flex size-4 shrink-0 items-center justify-center rounded border peer-focus-visible:ring-2 peer-focus-visible:ring-primary",
                      marcado ? "border-primary bg-primary text-white" : "border-line-strong bg-surface",
                    )}
                  >
                    {marcado && <Check className="size-3" strokeWidth={3} />}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink">{o.rotulo}</span>
                  {o.detalhe && <span className="text-xs text-faint">{o.detalhe}</span>}
                </label>
              );
            })}
            {!visiveis.length && <p className="px-2 py-3 text-sm text-muted">Nada encontrado para “{termo}”.</p>}
          </fieldset>
          {ativo && (
            <div className="mt-1 border-t border-line px-1 pt-1">
              <button
                type="button"
                onClick={() => onChange([])}
                className="w-full rounded-md px-2 py-1.5 text-left text-[13px] text-primary-ink hover:bg-primary-soft"
              >
                Limpar seleção
              </button>
            </div>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function gatilho(ativo: boolean) {
  return cn(
    "inline-flex h-8 items-center gap-1.5 rounded-control border px-2.5 text-[13px] transition-colors",
    ativo ? "border-primary/40 bg-primary-soft" : "border-line bg-surface hover:border-line-strong",
  );
}
