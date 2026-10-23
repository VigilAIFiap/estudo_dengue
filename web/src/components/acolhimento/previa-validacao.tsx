import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { rotuloCampo, rotuloInconsistencia, type ResultadoValidacao } from "@/lib/triagem";

/** Prévia, no navegador, do que o Oracle vai decidir. Não substitui a validação do banco. */
export function PreviaValidacao({ resultado }: { resultado: ResultadoValidacao }) {
  const { aprovavel, faltantes, inconsistencias, preenchidos, total } = resultado;
  const pct = total ? Math.round((preenchidos / total) * 100) : 0;
  const Icone = aprovavel ? CheckCircle2 : AlertTriangle;

  return (
    <section
      aria-labelledby="previa-titulo"
      className={`rounded-panel border p-4 ${aprovavel ? "border-baixo/40 bg-baixo-soft" : "border-medio/40 bg-medio-soft"}`}
    >
      <p className="text-xs font-medium tracking-wide text-muted uppercase">Prévia da validação</p>
      <h2 id="previa-titulo" className={`mt-1 flex items-start gap-2 text-[15px] font-semibold ${aprovavel ? "text-baixo-ink" : "text-medio-ink"}`}>
        <Icone aria-hidden className="mt-0.5 size-4 shrink-0" />
        {aprovavel ? "Pronto para aprovação automática" : "Irá para revisão no APEX"}
      </h2>

      <div className="mt-3">
        <div className="flex items-baseline justify-between text-xs text-ink-2">
          <span>Campos preenchidos</span>
          <span className="num font-medium">
            {preenchidos} de {total}
          </span>
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/70" aria-hidden>
          <div className={`h-full rounded-full ${aprovavel ? "bg-baixo" : "bg-medio"}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {inconsistencias.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-critico-ink">Inconsistências</p>
          <ul className="mt-1 list-disc pl-4 text-[13px] leading-5 text-ink-2">
            {inconsistencias.map((c) => (
              <li key={c}>{rotuloInconsistencia(c)}</li>
            ))}
          </ul>
        </div>
      )}

      {faltantes.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-ink-2">Faltam</p>
          <ul className="mt-1 flex flex-wrap gap-1">
            {faltantes.map((c) => (
              <li key={c} className="rounded-chip bg-white/70 px-1.5 py-0.5 text-xs text-ink-2">
                {rotuloCampo(c)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-3 border-t border-black/5 pt-2.5 text-xs leading-4 text-muted">
        Prévia no navegador. A decisão final é do Oracle, no envio.
      </p>
    </section>
  );
}
