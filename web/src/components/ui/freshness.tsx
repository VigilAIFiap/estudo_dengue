"use client";

import { useMeta } from "@/lib/queries";
import { fmtData, fmtDataHora } from "@/lib/format";
import * as Popover from "@radix-ui/react-popover";
import { cn } from "./cn";

/** Data da última notificação carregada, defasagem e procedência dos arquivos. */
export function DataFreshnessIndicator() {
  const { data, isError } = useMeta();
  if (isError) return <span className="text-xs text-critico-ink">API indisponível</span>;
  if (!data) return <span className="h-5 w-40 animate-shimmer rounded bg-sunken" aria-hidden />;
  const defasado = data.defasagem_dias > 30;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-control px-2 py-1 text-xs text-muted hover:bg-sunken"
        >
          <span
            aria-hidden
            className={cn("size-1.5 rounded-full", defasado ? "bg-medio" : "bg-baixo")}
          />
          <span>
            Dados até <span className="num font-medium text-ink">{fmtData(data.cobertura_fim)}</span>
            <span className="hidden lg:inline"> ({data.defasagem_dias} dias atrás)</span>
          </span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="z-50 w-80 rounded-control border border-line bg-surface p-4 text-[13px] leading-5 shadow-float"
        >
          <h2 className="font-semibold text-ink">Atualização dos dados</h2>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-muted">Notificações</dt>
            <dd className="num text-right text-ink">
              {fmtData(data.cobertura_inicio)} a {fmtData(data.cobertura_fim)}
            </dd>
            <dt className="text-muted">Defasagem</dt>
            <dd className="num text-right text-ink">{data.defasagem_dias} dias</dd>
            <dt className="text-muted">Processado em</dt>
            <dd className="num text-right text-ink">{fmtDataHora(data.carregado_em)}</dd>
            <dt className="text-muted">Extração SINAN</dt>
            <dd className="text-right text-ink">não informada nos arquivos</dd>
          </dl>
          <p className="mt-3 border-t border-line pt-3 text-xs text-muted">
            A data de notificação mais recente não garante que a base esteja completa até ela: notificações chegam com
            atraso e casos são reclassificados. As semanas finais tendem a subir em extrações futuras.
          </p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
