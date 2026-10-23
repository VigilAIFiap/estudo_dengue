import type { ReactNode } from "react";

/** Bloco de fórmula em fonte monoespaçada, com legenda opcional. */
export function Formula({ children, legenda }: { children: ReactNode; legenda?: string }) {
  return (
    <figure className="my-2">
      <pre className="overflow-x-auto rounded-control border border-line bg-sunken px-3 py-2.5 font-mono text-[12.5px] leading-6 text-ink">
        {children}
      </pre>
      {legenda && <figcaption className="mt-1 text-xs text-muted">{legenda}</figcaption>}
    </figure>
  );
}
