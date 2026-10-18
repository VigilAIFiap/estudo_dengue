"use client";

import Link from "next/link";
import type { Schemas } from "@/lib/api";
import { estiloNivel } from "@/lib/criticality";
import { fmtDec, fmtInt } from "@/lib/format";
import { useHrefComFiltros } from "@/components/shell/app-sidebar";
import { CriticalityBadge } from "./criticality-badge";
import { cn } from "./cn";

/** Lista compacta de municípios por score; barras na escala 0–100 (não relativa ao máximo). */
export function RankingList({
  itens,
  destaque,
  onEscolher,
}: {
  itens: Schemas["Municipio"][];
  destaque?: number | null;
  onEscolher?: (id: number) => void;
}) {
  const href = useHrefComFiltros();
  return (
    <ol className="flex flex-col">
      {itens.map((m) => {
        const estilo = estiloNivel(m.nivel);
        const conteudo = (
          <>
            <span className="num w-6 shrink-0 text-right text-xs text-faint">{m.posicao ?? "—"}</span>
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline justify-between gap-2">
                <span className="truncate text-[13.5px] text-ink">
                  {m.nome} <span className="text-xs text-muted">{m.uf}</span>
                </span>
                <span className="num shrink-0 text-[13px] font-medium text-ink">{m.score == null ? "—" : fmtDec(m.score)}</span>
              </span>
              <span className="mt-1 flex items-center gap-2">
                <span className="h-1 flex-1 rounded-full bg-sunken">
                  <span className="block h-full rounded-full" style={{ width: `${m.score ?? 0}%`, background: estilo?.fill ?? "#cbd5e1" }} />
                </span>
                <span className="num w-20 shrink-0 text-right text-xs text-muted">{fmtInt(m.notificacoes)} notif.</span>
              </span>
            </span>
            <span className="hidden shrink-0 sm:block">
              <CriticalityBadge nivel={m.nivel} compacto />
            </span>
          </>
        );
        const classe = cn(
          "flex w-full items-center gap-3 rounded-md px-1.5 py-2 text-left hover:bg-canvas",
          destaque === m.id_municip && "bg-primary-soft hover:bg-primary-soft",
        );
        return (
          <li key={m.id_municip}>
            {onEscolher ? (
              <button type="button" className={classe} onClick={() => onEscolher(m.id_municip)}>
                {conteudo}
              </button>
            ) : (
              <Link className={classe} href={`${href("/municipios")}${href("/municipios").includes("?") ? "&" : "?"}m=${m.id_municip}`}>
                {conteudo}
              </Link>
            )}
          </li>
        );
      })}
    </ol>
  );
}
