"use client";

import { CalendarRange, Database } from "lucide-react";
import { usePathname } from "next/navigation";
import { rotuloBase } from "@/lib/base-municipal";
import { fmtData } from "@/lib/format";
import { useFiltrosResolvidos } from "@/lib/queries";

/** Fonte dos dados e período analisado, no topo de cada tela de análise. */
export function FonteStrip() {
  const pathname = usePathname();
  const { meta, inicio, fim } = useFiltrosResolvidos();
  const dados = meta.data;
  if (!dados || pathname.startsWith("/pacientes")) return null;

  const base = dados.fonte_dados === "oracle" ? "Oracle Database (camada Prata)" : "arquivos CSV do SINAN";
  const de = inicio ?? dados.cobertura_inicio;
  const ate = fim ?? dados.cobertura_fim;

  return (
    <section
      aria-label="Fonte e período dos dados"
      className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-control border border-line border-l-[3px] border-l-teal bg-surface px-3.5 py-2 text-xs text-muted"
    >
      <p className="inline-flex items-center gap-1.5">
        <Database aria-hidden className="size-3.5 text-teal" />
        <span>
          Fonte: <span className="font-medium text-ink">SINAN / DATASUS</span> · notificações de dengue · base: {base} ·{" "}
          {rotuloBase(dados.base_municipal)}
        </span>
      </p>
      <p className="inline-flex items-center gap-1.5">
        <CalendarRange aria-hidden className="size-3.5 text-primary" />
        <span>
          Período analisado:{" "}
          <span className="num font-medium text-ink">
            {fmtData(de)} a {fmtData(ate)}
          </span>
          {pathname.startsWith("/previsoes") && <> · projeção pelo modelo SARIMA mensal</>}
        </span>
      </p>
    </section>
  );
}
