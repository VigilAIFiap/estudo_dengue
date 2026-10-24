import { AlertTriangle, CheckCircle2, ExternalLink } from "lucide-react";
import type { Schemas } from "@/lib/api";
import { rotuloCampo, rotuloInconsistencia } from "@/lib/triagem";

/** Desfecho devolvido pelo Oracle: aprovado na hora ou encaminhado à revisão no APEX. */
export function ResultadoTriagem({
  resultado,
  apexUrl,
}: {
  resultado: Schemas["PatientAssessmentCreated"];
  apexUrl?: string;
}) {
  const faltantes = resultado.campos_faltantes ?? [];
  const inconsistencias = resultado.inconsistencias ?? [];

  if (resultado.status === "APROVADO") {
    return (
      <div role="status" className="flex items-start gap-3 rounded-panel border border-baixo/40 bg-baixo-soft p-4">
        <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-baixo-ink" />
        <div className="text-sm leading-6 text-ink-2">
          <p className="text-[15px] font-semibold text-baixo-ink">Aprovado automaticamente</p>
          <p>
            Protocolo <span className="num font-medium text-ink">{resultado.intake_id}</span>. O registro passou nas
            regras do Oracle e já está na base aprovada.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div role="status" className="flex items-start gap-3 rounded-panel border border-medio/40 bg-medio-soft p-4">
      <AlertTriangle aria-hidden className="mt-0.5 size-5 shrink-0 text-medio-ink" />
      <div className="min-w-0 text-sm leading-6 text-ink-2">
        <p className="text-[15px] font-semibold text-medio-ink">Enviado para revisão no APEX</p>
        <p>
          Protocolo <span className="num font-medium text-ink">{resultado.intake_id}</span>. Um analista vai aprovar ou
          rejeitar o registro.
        </p>
        {inconsistencias.length > 0 && (
          <p className="mt-1">
            <span className="font-medium text-critico-ink">Inconsistências:</span>{" "}
            {inconsistencias.map(rotuloInconsistencia).join("; ")}.
          </p>
        )}
        {faltantes.length > 0 && (
          <p className="mt-1">
            <span className="font-medium text-ink">Campos faltantes:</span> {faltantes.map(rotuloCampo).join(", ")}.
          </p>
        )}
        {apexUrl && (
          <a
            href={apexUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-primary-ink hover:underline"
          >
            Abrir a fila no Oracle APEX <ExternalLink aria-hidden className="size-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
