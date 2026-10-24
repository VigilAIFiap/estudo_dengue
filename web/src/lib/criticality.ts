export const NIVEIS = ["Crítico", "Alto", "Médio", "Baixo"] as const;
export type Nivel = (typeof NIVEIS)[number];

type Estilo = { fill: string; ink: string; soft: string; barras: number; descricao: string };

/** Uma fonte de verdade para cor, intensidade e texto de cada nível. */
export const NIVEL: Record<Nivel, Estilo> = {
  Crítico: { fill: "#dc2626", ink: "#b91c1c", soft: "#fdeaea", barras: 4, descricao: "Score ≥ 50" },
  Alto: { fill: "#f97316", ink: "#c2410c", soft: "#feefe3", barras: 3, descricao: "Score de 35 a 49,9" },
  Médio: { fill: "#eab308", ink: "#a16207", soft: "#fdf6dc", barras: 2, descricao: "Score de 20 a 34,9" },
  Baixo: { fill: "#16a34a", ink: "#15803d", soft: "#e9f7ee", barras: 1, descricao: "Score < 20" },
};

export const SEM_SCORE = { fill: "#cbd5e1", ink: "#5b6678", descricao: "Volume abaixo do 1º quartil do recorte" };

export function estiloNivel(nivel: string | null | undefined) {
  return nivel && nivel in NIVEL ? NIVEL[nivel as Nivel] : null;
}
