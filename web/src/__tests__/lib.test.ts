import { describe, expect, it } from "vitest";
import { intervaloAnoEpi } from "@/lib/epi";
import { contarAtivos, escreverFiltros, lerFiltros, paraParametros } from "@/lib/filters";
import { fmtData, fmtInt, fmtVariacao } from "@/lib/format";
import { quebras } from "@/components/map/brazil-map";

describe("filtros na URL", () => {
  it("lê, valida e descarta valores inválidos", () => {
    const f = lerFiltros(new URLSearchParams("inicio=2026-01-04&uf=SP&uf=xx&municipio=abc&classificacao=10&classificacao=12"));
    expect(f.inicio).toBe("2026-01-04");
    expect(f.uf).toEqual([]); // um valor inválido invalida a lista inteira
    expect(f.municipio).toBeUndefined();
    expect(f.classificacao).toEqual([10, 12]);
  });

  it("aplica o período padrão só quando não há escolha explícita", () => {
    const padrao = { inicio: "2026-01-04", fim: "2026-05-10" };
    expect(paraParametros({ uf: ["SP"], classificacao: [] }, padrao).toString()).toBe("inicio=2026-01-04&fim=2026-05-10&uf=SP");
    expect(paraParametros({ inicio: "2025-01-01", uf: [], classificacao: [] }, padrao).get("inicio")).toBe("2025-01-01");
  });

  it("preserva parâmetros de página ao escrever filtros", () => {
    const p = escreverFiltros(new URLSearchParams("camada=score&uf=RJ"), { uf: ["SP", "MG"], classificacao: [] });
    expect(p.get("camada")).toBe("score");
    expect(p.getAll("uf")).toEqual(["MG", "SP"]);
  });

  it("conta filtros ativos", () => {
    expect(contarAtivos({ uf: [], classificacao: [] })).toBe(0);
    expect(contarAtivos({ inicio: "2026-01-01", fim: "2026-02-01", uf: ["SP"], municipio: 355030, classificacao: [10] })).toBe(4);
  });
});

describe("semana epidemiológica", () => {
  it("ano epidemiológico começa no domingo da semana com 4 de janeiro", () => {
    expect(intervaloAnoEpi(2025)).toEqual({ inicio: "2024-12-29", fim: "2026-01-03" });
    expect(intervaloAnoEpi(2026).inicio).toBe("2026-01-04");
  });
});

describe("formatação pt-BR", () => {
  it("formata sem depender de fuso horário", () => {
    expect(fmtData("2026-05-10")).toBe("10/05/2026");
    expect(fmtInt(1949481)).toBe("1.949.481");
    expect(fmtVariacao(-74.4)).toBe("−74,4%");
    expect(fmtVariacao(null)).toBe("—");
  });
});

describe("classes do mapa", () => {
  it("usa quantis apenas entre valores positivos e sem cortes repetidos", () => {
    const cortes = quebras([0, 0, 1, 1, 1, 2, 5, 10, 100, 1000], 4);
    expect(cortes).toEqual([...new Set(cortes)]);
    expect(cortes.every((c) => c > 0)).toBe(true);
    expect(quebras([0, 0])).toEqual([]);
  });
});
