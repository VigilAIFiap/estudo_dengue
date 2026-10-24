import { estiloNivel, SEM_SCORE } from "@/lib/criticality";
import { cn } from "./cn";

/** Nível de criticidade: quatro barras + rótulo, para não depender só da cor. */
export function CriticalityMeter({ nivel, className }: { nivel: string | null | undefined; className?: string }) {
  const estilo = estiloNivel(nivel);
  return (
    <span aria-hidden className={cn("inline-flex items-end gap-[2px]", className)}>
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="w-[3px] rounded-[1px]"
          style={{
            height: 4 + i * 2,
            background: estilo && i <= estilo.barras ? estilo.fill : "#dfe4ec",
          }}
        />
      ))}
    </span>
  );
}

export function CriticalityBadge({ nivel, compacto = false }: { nivel: string | null | undefined; compacto?: boolean }) {
  const estilo = estiloNivel(nivel);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-chip px-1.5 py-0.5 text-xs font-medium whitespace-nowrap"
      style={{ background: estilo?.soft ?? "#eef2f6", color: estilo?.ink ?? SEM_SCORE.ink }}
    >
      <CriticalityMeter nivel={nivel} />
      {!compacto && <span>{nivel ?? "Sem score"}</span>}
      {compacto && <span className="sr-only">{nivel ?? "Sem score"}</span>}
    </span>
  );
}
