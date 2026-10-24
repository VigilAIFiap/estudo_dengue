import { AlertOctagon, AlertTriangle, CircleAlert } from "lucide-react";
import type { Schemas } from "@/lib/api";
import { NIVEL, type Nivel } from "@/lib/criticality";

const ICONE = { Crítico: AlertOctagon, Alto: AlertTriangle, Médio: CircleAlert, Baixo: CircleAlert } as const;

/** Alertas analíticos: cada um exibe o critério que o disparou. */
export function AlertList({ alertas }: { alertas: Schemas["Alerta"][] }) {
  if (!alertas.length)
    return <p className="py-6 text-center text-sm text-muted">Nenhum critério de alerta foi atingido no recorte.</p>;
  return (
    <ul className="flex flex-col divide-y divide-line">
      {alertas.map((a) => {
        const Icone = ICONE[a.severidade as Nivel];
        const estilo = NIVEL[a.severidade as Nivel];
        return (
          <li key={a.id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md" style={{ background: estilo.soft }}>
              <Icone aria-hidden className="size-3.5" style={{ color: estilo.ink }} />
            </span>
            <div className="min-w-0">
              <p className="text-sm leading-5 font-medium text-ink">
                <span className="sr-only">Severidade {a.severidade}: </span>
                {a.titulo}
              </p>
              <p className="mt-0.5 text-xs leading-4 text-muted">{a.criterio}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
