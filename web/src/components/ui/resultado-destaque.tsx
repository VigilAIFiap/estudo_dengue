import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";
import type { Schemas } from "@/lib/api";
import { fmtDec, fmtInt, fmtVariacao } from "@/lib/format";
import { cn } from "./cn";

/** Leitura em uma frase do que o período mostra: onde a situação é mais grave e para onde olhar primeiro. */
export function ResultadoDestaque({ visao, hrefMapa }: { visao: Schemas["VisaoGeral"]; hrefMapa: string }) {
  const criticos = visao.niveis.find((n) => n.nivel === "Crítico")?.municipios ?? 0;
  const topo = visao.top_municipios[0];
  const variacao = visao.comparacao?.variacao_pct.notificacoes;
  const Icone = variacao == null || variacao === 0 ? Minus : variacao > 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <section
      aria-label="Resultado do período"
      className="mb-5 grid gap-4 rounded-panel border border-line bg-linear-to-r from-primary-soft via-surface to-teal-soft p-5 md:grid-cols-[1fr_auto] md:items-center"
    >
      <div className="min-w-0">
        <p className="text-xs font-medium tracking-wide text-muted uppercase">Resultado do período</p>
        <p className={cn("mt-1 text-title font-semibold", criticos > 0 ? "text-critico-ink" : "text-baixo-ink")}>
          {criticos > 0
            ? `${fmtInt(criticos)} ${criticos === 1 ? "município em nível crítico" : "municípios em nível crítico"}`
            : "Nenhum município em nível crítico"}
        </p>
        {topo && (
          <p className="mt-1 text-sm leading-6 text-ink-2">
            Maior pressão: <span className="font-medium text-ink">{topo.nome}/{topo.uf}</span>
            {topo.score != null && <> · score {fmtDec(topo.score)}</>} · {fmtInt(topo.notificacoes)} notificações.{" "}
            <Link href={hrefMapa} className="font-medium text-primary-ink hover:underline">
              Ver no mapa
            </Link>
          </p>
        )}
      </div>
      {variacao != null && (
        <div className="flex items-center gap-2 rounded-control bg-white/70 px-3.5 py-2.5">
          <Icone
            aria-hidden
            className={cn("size-6", variacao > 0 ? "text-critico-ink" : variacao < 0 ? "text-baixo-ink" : "text-muted")}
          />
          <div>
            <p className="num text-lg leading-6 font-semibold text-ink">{fmtVariacao(variacao)}</p>
            <p className="text-xs leading-4 text-muted">notificações vs. período comparável</p>
          </div>
        </div>
      )}
    </section>
  );
}
