import type { Schemas } from "./api";

type Envio = Schemas["PatientAssessmentSubmission"];

export type CampoTriagem = keyof Envio;
export type ValoresTriagem = { [C in CampoTriagem]-?: Exclude<Envio[C], null | undefined> | "" };

export const VALORES_INICIAIS: ValoresTriagem = {
  age_group: "",
  sex: "",
  symptom_duration: "",
  fever: "",
  headache: "",
  muscle_pain: "",
  rash: "",
  nausea: "",
  vomiting: "",
  pregnancy: "",
  comorbidities: "",
};

export function paraEnvio(v: ValoresTriagem): Envio {
  return {
    age_group: v.age_group || null,
    sex: v.sex || null,
    symptom_duration: v.symptom_duration || null,
    fever: v.fever || null,
    headache: v.headache || null,
    muscle_pain: v.muscle_pain || null,
    rash: v.rash || null,
    nausea: v.nausea || null,
    vomiting: v.vomiting || null,
    pregnancy: v.pregnancy || null,
    comorbidities: v.comorbidities || null,
  };
}

/** Códigos iguais aos devolvidos pelo Oracle (VIGIL_TRIAGE_REVIEW.CAMPOS_FALTANTES), na mesma ordem. */
export const CAMPOS_OBRIGATORIOS: { chave: CampoTriagem; codigo: string; rotulo: string }[] = [
  { chave: "age_group", codigo: "FAIXA_ETARIA", rotulo: "Faixa etária" },
  { chave: "sex", codigo: "SEXO", rotulo: "Sexo" },
  { chave: "symptom_duration", codigo: "TEMPO_SINTOMAS", rotulo: "Início dos sintomas" },
  { chave: "fever", codigo: "FEBRE", rotulo: "Febre" },
  { chave: "headache", codigo: "CEFALEIA", rotulo: "Dor de cabeça" },
  { chave: "muscle_pain", codigo: "DOR_MUSCULAR", rotulo: "Dor muscular" },
  { chave: "rash", codigo: "ERUPCAO_CUTANEA", rotulo: "Manchas ou erupção na pele" },
  { chave: "nausea", codigo: "NAUSEA", rotulo: "Náusea" },
  { chave: "vomiting", codigo: "VOMITO", rotulo: "Vômito" },
  { chave: "pregnancy", codigo: "GESTACAO", rotulo: "Gestação" },
  { chave: "comorbidities", codigo: "COMORBIDADES", rotulo: "Comorbidades" },
];

export const ROTULO_INCONSISTENCIA: Record<string, string> = {
  GESTACAO_INCOMPATIVEL_COM_SEXO: "Gestação informada para sexo masculino",
  GESTACAO_INCOMPATIVEL_COM_IDADE: "Gestação informada para a faixa de 0 a 9 anos",
};

const IDADES_SEM_GESTACAO = ["0-4", "5-9"];

/** Gestação só se aplica a quem não é do sexo masculino e tem 10 anos ou mais. */
export function gestacaoSeAplica(v: Pick<ValoresTriagem, "sex" | "age_group">): boolean {
  return !(v.sex === "M" || IDADES_SEM_GESTACAO.includes(v.age_group));
}

export type ResultadoValidacao = {
  faltantes: string[];
  inconsistencias: string[];
  total: number;
  preenchidos: number;
  aprovavel: boolean;
};

/**
 * Prévia no navegador das regras que o Oracle aplica no envio. A decisão final é sempre do banco.
 */
export function validarTriagem(v: ValoresTriagem): ResultadoValidacao {
  const aplicavel = gestacaoSeAplica(v);
  const faltantes: string[] = [];
  for (const campo of CAMPOS_OBRIGATORIOS) {
    if (campo.chave === "pregnancy" && !aplicavel) continue;
    if (v[campo.chave] === "") faltantes.push(campo.codigo);
  }

  const inconsistencias: string[] = [];
  if (v.pregnancy === "SIM") {
    if (v.sex === "M") inconsistencias.push("GESTACAO_INCOMPATIVEL_COM_SEXO");
    if (IDADES_SEM_GESTACAO.includes(v.age_group)) inconsistencias.push("GESTACAO_INCOMPATIVEL_COM_IDADE");
  }

  const total = CAMPOS_OBRIGATORIOS.length - (aplicavel ? 0 : 1);
  return {
    faltantes,
    inconsistencias,
    total,
    preenchidos: total - faltantes.length,
    aprovavel: faltantes.length === 0 && inconsistencias.length === 0,
  };
}

export function rotuloCampo(codigo: string): string {
  return CAMPOS_OBRIGATORIOS.find((c) => c.codigo === codigo)?.rotulo ?? codigo;
}

export function rotuloInconsistencia(codigo: string): string {
  return ROTULO_INCONSISTENCIA[codigo] ?? codigo;
}
