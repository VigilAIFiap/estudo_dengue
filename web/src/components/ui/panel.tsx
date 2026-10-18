import type { ReactNode } from "react";
import { cn } from "./cn";

type Props = {
  titulo: string;
  subtitulo?: ReactNode;
  acoes?: ReactNode;
  rodape?: ReactNode;
  children: ReactNode;
  className?: string;
  corpoClassName?: string;
  id?: string;
};

/** Painel padrão para gráficos e tabelas: título descritivo, contexto e fonte. */
export function Panel({ titulo, subtitulo, acoes, rodape, children, className, corpoClassName, id }: Props) {
  const tituloId = id ? `${id}-titulo` : undefined;
  return (
    <section
      aria-labelledby={tituloId}
      className={cn("flex min-w-0 flex-col rounded-panel border border-line bg-surface", className)}
    >
      <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
        <div className="min-w-0">
          <h2 id={tituloId} className="text-[15px] leading-5 font-semibold text-ink">
            {titulo}
          </h2>
          {subtitulo && <p className="mt-0.5 text-[13px] leading-5 text-muted">{subtitulo}</p>}
        </div>
        {acoes && <div className="flex shrink-0 items-center gap-2">{acoes}</div>}
      </header>
      <div className={cn("min-w-0 flex-1 px-5 pb-4", corpoClassName)}>{children}</div>
      {rodape && <footer className="border-t border-line px-5 py-2.5 text-xs leading-4 text-muted">{rodape}</footer>}
    </section>
  );
}
