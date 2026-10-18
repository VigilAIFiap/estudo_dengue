"use client";

import { flexRender, getCoreRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { Schemas } from "@/lib/api";
import { fmtDec, fmtInt, fmtPct } from "@/lib/format";
import { CriticalityBadge } from "@/components/ui/criticality-badge";
import { cn } from "@/components/ui/cn";

type Linha = Schemas["Municipio"];

type Props = {
  itens: Linha[];
  ordenacao: SortingState;
  onOrdenar: (s: SortingState) => void;
  selecionados: number[];
  onAlternarSelecao: (id: number) => void;
  onAbrir: (id: number) => void;
  destaque?: number | null;
  carregando?: boolean;
  limiteSelecao: number;
};

const numero = (fmt: (v: number) => string) => (v: unknown) => (v == null ? "—" : fmt(v as number));

/** Tabela analítica: ordenação e paginação acontecem no servidor (manual). */
export function MunicipalityTable({
  itens,
  ordenacao,
  onOrdenar,
  selecionados,
  onAlternarSelecao,
  onAbrir,
  destaque,
  carregando,
  limiteSelecao,
}: Props) {
  const colunas: ColumnDef<Linha>[] = [
    {
      id: "selecionar",
      enableSorting: false,
      header: () => <span className="sr-only">Selecionar para comparar</span>,
      cell: ({ row }) => {
        const marcado = selecionados.includes(row.original.id_municip);
        const bloqueado = !marcado && selecionados.length >= limiteSelecao;
        return (
          <input
            type="checkbox"
            aria-label={`Comparar ${row.original.nome}`}
            checked={marcado}
            disabled={bloqueado}
            onChange={() => onAlternarSelecao(row.original.id_municip)}
            className="size-4 accent-[#2563eb] disabled:opacity-40"
          />
        );
      },
    },
    { accessorKey: "posicao", header: "#", enableSorting: false, cell: (c) => <span className="text-faint">{c.getValue<number | null>() ?? "—"}</span> },
    {
      accessorKey: "nome",
      header: "Município",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => onAbrir(row.original.id_municip)}
          className="text-left font-medium text-ink hover:text-primary-ink hover:underline"
        >
          {row.original.nome}
          {row.original.capital && <span className="ml-1.5 text-2xs font-normal text-muted">capital</span>}
        </button>
      ),
    },
    { accessorKey: "uf", header: "UF" },
    { accessorKey: "notificacoes", header: "Notificações", cell: (c) => numero(fmtInt)(c.getValue()) },
    { accessorKey: "confirmados", header: "Confirmados", cell: (c) => numero(fmtInt)(c.getValue()) },
    { accessorKey: "graves", header: "Alarme/grave", cell: (c) => numero(fmtInt)(c.getValue()) },
    { accessorKey: "obitos_dengue", header: "Óbitos", cell: (c) => numero(fmtInt)(c.getValue()) },
    { accessorKey: "hospitalizacoes", header: "Hospitalizações", cell: (c) => numero(fmtInt)(c.getValue()) },
    { accessorKey: "taxa_hospitalizacao", header: "Tx. hosp.", cell: (c) => fmtPct(c.getValue<number | null>()) },
    { accessorKey: "letalidade", header: "Letalidade", cell: (c) => fmtPct(c.getValue<number | null>(), 2) },
    { id: "score_criticidade", accessorKey: "score", header: "Score", cell: (c) => numero(fmtDec)(c.getValue()) },
    { accessorKey: "nivel", header: "Nível", enableSorting: false, cell: (c) => <CriticalityBadge nivel={c.getValue<string | null>()} /> },
  ];

  // O projeto não usa o React Compiler; a tabela re-renderiza a cada página do servidor.
  // eslint-disable-next-line react-hooks/incompatible-library
  const tabela = useReactTable({
    data: itens,
    columns: colunas,
    state: { sorting: ordenacao },
    manualSorting: true,
    manualPagination: true,
    enableSortingRemoval: false,
    onSortingChange: (u) => onOrdenar(typeof u === "function" ? u(ordenacao) : u),
    getCoreRowModel: getCoreRowModel(),
    getRowId: (r) => String(r.id_municip),
  });

  const textuais = new Set(["nome", "uf", "nivel", "selecionar"]);

  return (
    <div className={cn("overflow-x-auto rounded-control border border-line transition-opacity", carregando && "opacity-60")} aria-busy={carregando}>
      <table className="w-full min-w-[1040px] text-[13px]">
        <caption className="sr-only">Municípios ordenados; use os cabeçalhos para mudar a ordenação</caption>
        <thead className="bg-canvas text-xs text-muted">
          {tabela.getHeaderGroups().map((g) => (
            <tr key={g.id}>
              {g.headers.map((h) => {
                const ordem = h.column.getIsSorted();
                const direita = !textuais.has(h.column.id) && h.column.id !== "posicao";
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={ordem === "asc" ? "ascending" : ordem === "desc" ? "descending" : undefined}
                    className={cn("px-2.5 py-2 font-medium whitespace-nowrap", direita ? "text-right" : "text-left")}
                  >
                    {h.column.getCanSort() ? (
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className={cn("inline-flex items-center gap-1 hover:text-ink", ordem && "text-ink", direita && "flex-row-reverse")}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {ordem === "asc" ? (
                          <ArrowUp aria-hidden className="size-3" />
                        ) : ordem === "desc" ? (
                          <ArrowDown aria-hidden className="size-3" />
                        ) : (
                          <ArrowUpDown aria-hidden className="size-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {tabela.getRowModel().rows.map((r) => (
            <tr
              key={r.id}
              className={cn("border-t border-line hover:bg-canvas/70", destaque === r.original.id_municip && "bg-primary-soft/60")}
            >
              {r.getVisibleCells().map((c) => (
                <td
                  key={c.id}
                  className={cn(
                    "px-2.5 py-2 whitespace-nowrap",
                    !textuais.has(c.column.id) && c.column.id !== "posicao" ? "num text-right text-ink" : "text-ink-2",
                  )}
                >
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
