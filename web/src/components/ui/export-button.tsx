import { Download } from "lucide-react";
import { ButtonLink } from "./button";

/** Download direto de CSV gerado pela API com os filtros ativos. */
export function ExportButton({ href, children = "Exportar CSV" }: { href: string; children?: string }) {
  return (
    <ButtonLink href={href} download variante="secundario">
      <Download aria-hidden className="size-3.5" />
      {children}
    </ButtonLink>
  );
}
