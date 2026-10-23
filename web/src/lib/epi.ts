/** Semana epidemiológica: semana domingo–sábado; a SE 1 contém 4 de janeiro. */
export function inicioAnoEpi(ano: number): Date {
  const jan4 = new Date(Date.UTC(ano, 0, 4));
  return new Date(jan4.getTime() - jan4.getUTCDay() * 86_400_000);
}

export const isoData = (d: Date) => d.toISOString().slice(0, 10);

export function intervaloAnoEpi(ano: number): { inicio: string; fim: string } {
  const fim = new Date(inicioAnoEpi(ano + 1).getTime() - 86_400_000);
  return { inicio: isoData(inicioAnoEpi(ano)), fim: isoData(fim) };
}

/** Limita um intervalo à cobertura dos dados. */
export function limitar(i: { inicio: string; fim: string }, min: string, max: string) {
  return { inicio: i.inicio < min ? min : i.inicio, fim: i.fim > max ? max : i.fim };
}
