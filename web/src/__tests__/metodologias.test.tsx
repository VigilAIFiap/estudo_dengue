import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Methodology } from "@/components/municipios/methodology";
import { MetodologiaPrevisao } from "@/components/previsoes/metodologia-previsao";
import type { Schemas } from "@/lib/api";

vi.mock("@/lib/base-municipal", () => ({ useRotuloBase: () => "município de residência" }));

const METODOLOGIA: Schemas["Metodologia"] = {
  pesos: { taxa_obito: 0.6, taxa_hospitalizacao: 0.4 },
  suavizacao_casos: 50,
  q1: 8,
  cortes: [
    { nivel: "Crítico", minimo: 50 },
    { nivel: "Alto", minimo: 35 },
    { nivel: "Médio", minimo: 20 },
    { nivel: "Baixo", minimo: null },
  ],
};

describe("metodologia do score", () => {
  it("mostra a fórmula com os parâmetros devolvidos pela API", () => {
    render(<Methodology m={METODOLOGIA} />);
    const corpo = document.body;
    expect(corpo).toHaveTextContent("score = 100 × V × S");
    expect(corpo).toHaveTextContent("S = 0,6 × P(óbito*) + 0,4 × P(hosp*)");
    expect(corpo).toHaveTextContent("com k = 50");
    expect(corpo).toHaveTextContent("município de residência");
  });

  it("percorre um exemplo numérico até o nível", () => {
    render(<Methodology m={METODOLOGIA} />);
    expect(document.body).toHaveTextContent("V = 0,68");
    expect(document.body).toHaveTextContent("S = 0,86");
    expect(document.body).toHaveTextContent("58,5, nível Crítico");
  });

  it("lista as faixas e os limites do score", () => {
    render(<Methodology m={METODOLOGIA} />);
    expect(screen.getByText("Faixas do score")).toBeInTheDocument();
    expect(screen.getByText("Baixo")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("o score é relativo");
  });
});

describe("metodologia da previsão", () => {
  it("explica série, modelo, validação e como ler o resultado", () => {
    render(<MetodologiaPrevisao dataReferencia="2026-05-10" />);
    const corpo = document.body;
    expect(corpo).toHaveTextContent("SARIMA(p, d, q)(P, D, Q)₁₂");
    expect(corpo).toHaveTextContent("φ(B) · Φ(B^12) · (1 − B)^d · (1 − B^12)^D · y_t");
    expect(corpo).toHaveTextContent("menor AIC");
    expect(corpo).toHaveTextContent("MAE = (1 / n) × Σ | y_t − ŷ_t |");
    expect(corpo).toHaveTextContent("Como ler o resultado");
  });

  it("informa o tamanho mínimo da série para ajustar e para validar", () => {
    render(<MetodologiaPrevisao dataReferencia="2026-05-10" />);
    expect(document.body).toHaveTextContent("24 meses completos para ajustar o modelo");
    expect(document.body).toHaveTextContent("exige 33");
  });
});
