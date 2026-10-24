import { Lightbulb } from "lucide-react";
import type { Schemas } from "@/lib/api";

export function InsightCard({ insight }: { insight: Schemas["Insight"] }) {
  return (
    <article className="flex flex-col gap-2 rounded-panel border border-line bg-surface p-4">
      <Lightbulb aria-hidden className="size-4 text-teal" />
      <h3 className="text-sm leading-5 font-medium text-ink">{insight.titulo}</h3>
      <p className="text-[13px] leading-5 text-ink-2">{insight.detalhe}</p>
      <p className="mt-auto pt-1 text-xs leading-4 text-muted">
        <span className="font-medium">Origem:</span> {insight.origem}
      </p>
    </article>
  );
}
