"use client";

import type { ReactNode } from "react";
import { ErrorState } from "@/components/ui/states";
import { useMeta } from "@/lib/queries";

/** Sem metadados (cobertura e período padrão) nenhum painel consegue consultar: mostra o erro no topo. */
export function ApiGate({ children }: { children: ReactNode }) {
  const meta = useMeta();
  if (meta.isError)
    return (
      <div className="flex flex-col gap-3">
        <ErrorState erro={meta.error} tentarNovamente={() => meta.refetch()} />
        <p className="text-[13px] text-muted">Os painéis aparecem assim que a API responder.</p>
      </div>
    );
  return children;
}
