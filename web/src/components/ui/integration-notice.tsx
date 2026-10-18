import { PlugZap } from "lucide-react";
import type { ReactNode } from "react";

export function IntegrationNotice({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="mb-5 flex flex-col gap-3 rounded-panel border border-medio/40 bg-medio-soft p-5 sm:flex-row sm:items-start">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-white/70">
        <PlugZap aria-hidden className="size-5 text-medio-ink" />
      </span>
      <div className="min-w-0 text-sm leading-6 text-ink-2">
        <h2 className="text-[15px] font-semibold text-ink">{titulo}</h2>
        {children}
      </div>
    </section>
  );
}
