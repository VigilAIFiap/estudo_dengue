/** Cores de séries (validadas com o validador de paleta: CVD e contraste). */
export const SERIE = {
  principal: "#2563eb",
  principalClaro: "#bcd0fa",
  complementar: "#0f9d9a",
  anterior: "#98a3b5",
  grade: "#e8edf3",
  eixo: "#5b6678",
};

export const EIXO = {
  tick: { fill: SERIE.eixo, fontSize: 11 },
  axisLine: false,
  tickLine: false,
} as const;
