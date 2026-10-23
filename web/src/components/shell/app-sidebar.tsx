"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { paraParametros, lerFiltros } from "@/lib/filters";
import { cn } from "@/components/ui/cn";
import { BrandMark } from "./brand";
import { NAV_ANALISE, NAV_OPERACAO, type ItemNav } from "./nav";

/** Mantém os filtros globais ao trocar de página. */
export function useHrefComFiltros() {
  const params = useSearchParams();
  const qs = paraParametros(lerFiltros(new URLSearchParams(params.toString()))).toString();
  return (href: string) => (qs ? `${href}?${qs}` : href);
}

function useStatusModulos(): Record<string, string | undefined> {
  return {
    "/pacientes": "Validação automática + revisão no APEX",
  };
}

export function NavList({ recolhida = false, aoNavegar }: { recolhida?: boolean; aoNavegar?: () => void }) {
  const pathname = usePathname();
  const href = useHrefComFiltros();
  const status = useStatusModulos();

  const item = (i: ItemNav) => {
    const ativo = i.href === "/" ? pathname === "/" : pathname.startsWith(i.href);
    const Icone = i.icone;
    return (
      <li key={i.href}>
        <Link
          href={href(i.href)}
          onClick={aoNavegar}
          aria-current={ativo ? "page" : undefined}
          title={recolhida ? i.rotulo : undefined}
          className={cn(
            "group flex items-center gap-2.5 rounded-control px-2.5 py-2 text-[13.5px] transition-colors",
            ativo ? "bg-primary-soft font-medium text-primary-ink" : "text-ink-2 hover:bg-sunken hover:text-ink",
            recolhida && "justify-center px-0",
          )}
        >
          <Icone aria-hidden className={cn("size-[18px] shrink-0", ativo ? "text-primary" : "text-faint group-hover:text-ink-2")} />
          {!recolhida && (
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate">{i.rotulo}</span>
              {status[i.href] && <span className="truncate text-2xs font-normal text-faint">{status[i.href]}</span>}
            </span>
          )}
          {recolhida && <span className="sr-only">{i.rotulo}</span>}
        </Link>
      </li>
    );
  };

  return (
    <nav aria-label="Principal" className="flex flex-col gap-5">
      <ul className="flex flex-col gap-0.5">{NAV_ANALISE.map(item)}</ul>
      <div>
        {!recolhida && <p className="mb-1.5 px-2.5 text-xs text-faint">Triagem</p>}
        {recolhida && <hr className="mx-3 mb-2 border-line" />}
        <ul className="flex flex-col gap-0.5">{NAV_OPERACAO.map(item)}</ul>
      </div>
    </nav>
  );
}

export function AppSidebar({ recolhida, alternar }: { recolhida: boolean; alternar: () => void }) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-200 md:flex",
        recolhida ? "w-[68px]" : "w-[244px]",
      )}
    >
      <div className={cn("flex h-14 items-center gap-2.5 px-4", recolhida && "justify-center px-0")}>
        <BrandMark />
        {!recolhida && (
          <div className="leading-tight">
            <p className="text-[15px] font-semibold tracking-tight text-ink">Vigil</p>
            <p className="text-xs text-muted">Vigilância da dengue</p>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3">
        <NavList recolhida={recolhida} />
      </div>
      <div className={cn("border-t border-line p-3", recolhida && "flex justify-center")}>
        <button
          type="button"
          onClick={alternar}
          aria-label={recolhida ? "Expandir menu" : "Recolher menu"}
          className="inline-flex items-center gap-2 rounded-control px-2.5 py-1.5 text-[13px] text-muted hover:bg-sunken hover:text-ink"
        >
          {recolhida ? <PanelLeftOpen aria-hidden className="size-4" /> : <PanelLeftClose aria-hidden className="size-4" />}
          {!recolhida && "Recolher menu"}
        </button>
      </div>
    </aside>
  );
}
