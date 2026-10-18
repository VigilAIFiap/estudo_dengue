import { AlertCircle, Inbox, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "./cn";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-shimmer rounded-md bg-sunken", className)} />;
}

export function LoadingState({ altura = 240, rotulo = "Carregando dados" }: { altura?: number; rotulo?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2" style={{ height: altura }}>
      <span className="sr-only">{rotulo}…</span>
      <Skeleton className="h-full w-full" />
    </div>
  );
}

export function ErrorState({ erro, tentarNovamente }: { erro: unknown; tentarNovamente?: () => void }) {
  const mensagem = erro instanceof Error ? erro.message : "Erro inesperado ao consultar a API.";
  return (
    <div role="alert" className="flex items-start gap-3 rounded-control border border-critico/25 bg-critico-soft px-4 py-3">
      <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0 text-critico-ink" />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-medium text-critico-ink">A consulta falhou</p>
        <p className="mt-0.5 text-ink-2">{mensagem}</p>
      </div>
      {tentarNovamente && (
        <button
          type="button"
          onClick={tentarNovamente}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-critico-ink hover:bg-white/60"
        >
          <RotateCw aria-hidden className="size-3.5" /> Tentar de novo
        </button>
      )}
    </div>
  );
}

export function EmptyState({ titulo, children, icone }: { titulo: string; children?: ReactNode; icone?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <span aria-hidden className="text-faint">
        {icone ?? <Inbox className="size-6" />}
      </span>
      <p className="text-sm font-medium text-ink">{titulo}</p>
      {children && <div className="max-w-md text-[13px] leading-5 text-muted">{children}</div>}
    </div>
  );
}
