"use client";

import { Search } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";
import type { Schemas } from "@/lib/api";
import { useBuscaMunicipios } from "@/lib/queries";
import { useDebounce } from "@/lib/use-debounce";
import { cn } from "./cn";

type Municipio = Schemas["MunicipioBusca"];

/** Combobox acessível (padrão ARIA 1.2) para buscar municípios com notificações. */
export function MunicipioCombobox({
  onSelecionar,
  placeholder = "Buscar município",
  className,
  autoFocus,
}: {
  onSelecionar: (m: Municipio) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
}) {
  const id = useId();
  const [termo, setTermo] = useState("");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const atrasado = useDebounce(termo, 200);
  const { data = [], isFetching } = useBuscaMunicipios(atrasado);
  const visivel = aberto && termo.trim().length >= 2;

  const escolher = (m: Municipio | undefined) => {
    if (!m) return;
    onSelecionar(m);
    setTermo("");
    setAberto(false);
  };

  const teclado = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAberto(true);
      setAtivo((a) => Math.min(a + 1, data.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && visivel) {
      e.preventDefault();
      escolher(data[ativo]);
    } else if (e.key === "Escape") {
      setAberto(false);
    }
  };

  return (
    <div className={cn("relative", className)}>
      <label className="flex h-9 items-center gap-2 rounded-control border border-line bg-canvas px-2.5 focus-within:border-primary/50 focus-within:bg-surface">
        <Search aria-hidden className="size-4 shrink-0 text-faint" />
        <span className="sr-only">{placeholder}</span>
        <input
          role="combobox"
          aria-expanded={visivel}
          aria-controls={`${id}-lista`}
          aria-autocomplete="list"
          aria-activedescendant={visivel && data[ativo] ? `${id}-${data[ativo].id_municip}` : undefined}
          autoFocus={autoFocus}
          value={termo}
          onChange={(e) => {
            setTermo(e.target.value);
            setAberto(true);
            setAtivo(0);
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 120)}
          onKeyDown={teclado}
          placeholder={placeholder}
          className="h-full w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-faint"
        />
      </label>
      {visivel && (
        <ul
          id={`${id}-lista`}
          role="listbox"
          aria-label="Municípios encontrados"
          className="absolute top-full right-0 left-0 z-40 mt-1 max-h-80 overflow-y-auto rounded-control border border-line bg-surface p-1 shadow-float"
        >
          {data.map((m, i) => (
            <li
              key={m.id_municip}
              id={`${id}-${m.id_municip}`}
              role="option"
              aria-selected={i === ativo}
              onMouseDown={(e) => {
                e.preventDefault();
                escolher(m);
              }}
              onMouseEnter={() => setAtivo(i)}
              className={cn(
                "flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-sm",
                i === ativo ? "bg-primary-soft text-primary-ink" : "text-ink",
              )}
            >
              <span className="truncate">{m.nome}</span>
              <span className="ml-3 text-xs text-muted">{m.uf}</span>
            </li>
          ))}
          {!data.length && (
            <li className="px-2.5 py-2 text-sm text-muted">
              {isFetching ? "Buscando…" : "Nenhum município com notificações para esse nome."}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
