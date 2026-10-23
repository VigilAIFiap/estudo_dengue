const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const decimal1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const fmtInt = (n: number) => inteiro.format(n);
export const fmtCompacto = (n: number) => compacto.format(n);
export const fmtDec = (n: number) => decimal1.format(n);
export const fmtPct = (fracao: number | null | undefined, casas = 1) =>
  fracao == null
    ? "—"
    : new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: casas, maximumFractionDigits: casas }).format(
        fracao,
      );

export function fmtVariacao(pct: number | null | undefined): string {
  if (pct == null) return "—";
  const sinal = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sinal}${decimal1.format(Math.abs(pct))}%`;
}

/** "2026-05-10" → "10/05/2026" sem passar por fuso horário. */
export function fmtData(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function fmtMes(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES[Number(m) - 1]}/${a?.slice(2)}`;
}

export function fmtDataCurta(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(d)} ${MESES[Number(m) - 1]}`;
}

export function fmtDataHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(iso));
}
