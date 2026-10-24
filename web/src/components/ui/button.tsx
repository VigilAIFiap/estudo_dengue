import type { ButtonHTMLAttributes, AnchorHTMLAttributes } from "react";
import { cn } from "./cn";

type Variante = "primario" | "secundario" | "fantasma";

const base =
  "inline-flex items-center justify-center gap-1.5 rounded-control text-[13px] font-medium whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50 h-8 px-3";
const variantes: Record<Variante, string> = {
  primario: "bg-primary text-white hover:bg-primary-ink",
  secundario: "border border-line bg-surface text-ink hover:border-line-strong hover:bg-canvas",
  fantasma: "text-ink-2 hover:bg-sunken hover:text-ink",
};

export function Button({
  variante = "secundario",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  return <button type="button" className={cn(base, variantes[variante], className)} {...props} />;
}

export function ButtonLink({
  variante = "secundario",
  className,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variante?: Variante }) {
  return <a className={cn(base, variantes[variante], className)} {...props} />;
}
