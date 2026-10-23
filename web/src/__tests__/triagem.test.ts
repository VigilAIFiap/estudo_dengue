import { describe, expect, it } from "vitest";
import {
  VALORES_INICIAIS,
  gestacaoSeAplica,
  paraEnvio,
  rotuloCampo,
  rotuloInconsistencia,
  validarTriagem,
  type ValoresTriagem,
} from "@/lib/triagem";

const COMPLETO: ValoresTriagem = {
  age_group: "20-39",
  sex: "F",
  symptom_duration: "1-3_DIAS",
  fever: "SIM",
  headache: "SIM",
  muscle_pain: "SIM",
  rash: "NAO",
  nausea: "NAO",
  vomiting: "NAO",
  pregnancy: "NAO",
  comorbidities: "NAO",
};

describe("regras do acolhimento", () => {
  it("formulário vazio lista os 11 campos, na ordem do Oracle", () => {
    const r = validarTriagem(VALORES_INICIAIS);
    expect(r.faltantes).toHaveLength(11);
    expect(r.faltantes[0]).toBe("FAIXA_ETARIA");
    expect(r.faltantes[10]).toBe("COMORBIDADES");
    expect(r.aprovavel).toBe(false);
  });

  it("registro completo e consistente é aprovável", () => {
    const r = validarTriagem(COMPLETO);
    expect(r).toMatchObject({ faltantes: [], inconsistencias: [], total: 11, preenchidos: 11, aprovavel: true });
  });

  it("gestação em branco só é aceita quando não se aplica", () => {
    const homem = { ...COMPLETO, sex: "M" as const, pregnancy: "" as const };
    expect(validarTriagem(homem)).toMatchObject({ aprovavel: true, total: 10 });
    const crianca = { ...COMPLETO, age_group: "5-9" as const, pregnancy: "" as const };
    expect(validarTriagem(crianca).aprovavel).toBe(true);
    const mulher = { ...COMPLETO, pregnancy: "" as const };
    expect(validarTriagem(mulher).faltantes).toEqual(["GESTACAO"]);
  });

  it("aponta gestação incompatível com sexo e com idade", () => {
    const homem = validarTriagem({ ...COMPLETO, sex: "M", pregnancy: "SIM" });
    expect(homem.inconsistencias).toEqual(["GESTACAO_INCOMPATIVEL_COM_SEXO"]);
    expect(homem.aprovavel).toBe(false);
    const crianca = validarTriagem({ ...COMPLETO, age_group: "0-4", pregnancy: "SIM" });
    expect(crianca.inconsistencias).toEqual(["GESTACAO_INCOMPATIVEL_COM_IDADE"]);
  });

  it("sexo desconhecido não dispensa a pergunta de gestação", () => {
    expect(gestacaoSeAplica({ sex: "", age_group: "" })).toBe(true);
    expect(gestacaoSeAplica({ sex: "OUTRO", age_group: "20-39" })).toBe(true);
    expect(gestacaoSeAplica({ sex: "M", age_group: "20-39" })).toBe(false);
  });

  it("converte vazio em nulo no envio e traduz os códigos", () => {
    expect(paraEnvio({ ...VALORES_INICIAIS, fever: "SIM" })).toMatchObject({ fever: "SIM", sex: null, pregnancy: null });
    expect(rotuloCampo("ERUPCAO_CUTANEA")).toBe("Manchas ou erupção na pele");
    expect(rotuloCampo("CODIGO_NOVO")).toBe("CODIGO_NOVO");
    expect(rotuloInconsistencia("GESTACAO_INCOMPATIVEL_COM_SEXO")).toBe("Gestação informada para sexo masculino");
  });
});
