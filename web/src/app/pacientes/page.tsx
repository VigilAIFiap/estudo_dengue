"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { IntegrationNotice } from "@/components/ui/integration-notice";
import { Panel } from "@/components/ui/panel";
import { apiPost, type Schemas } from "@/lib/api";

type AssessmentForm = Schemas["PatientAssessmentSubmission"];
type AssessmentValues = {
  [Field in keyof AssessmentForm]-?: Exclude<AssessmentForm[Field], null | undefined> | "";
};

const INITIAL_VALUES: AssessmentValues = {
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

const OPCOES_IDADE = [
  ["0-4", "0 a 4 anos"],
  ["5-9", "5 a 9 anos"],
  ["10-19", "10 a 19 anos"],
  ["20-39", "20 a 39 anos"],
  ["40-59", "40 a 59 anos"],
  ["60+", "60 anos ou mais"],
];
const OPCOES_SIM_NAO = [
  ["SIM", "Sim"],
  ["NAO", "Não"],
];
const CAMPOS_SINTOMAS: { chave: keyof AssessmentForm; rotulo: string }[] = [
  { chave: "fever", rotulo: "Febre" },
  { chave: "headache", rotulo: "Dor de cabeça" },
  { chave: "muscle_pain", rotulo: "Dor muscular" },
  { chave: "rash", rotulo: "Manchas ou erupção na pele" },
  { chave: "nausea", rotulo: "Náusea" },
  { chave: "vomiting", rotulo: "Vômito" },
];

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: keyof AssessmentForm;
  label: string;
  value: string;
  options: string[][];
  onChange: (id: keyof AssessmentForm, value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-ink-2" htmlFor={id}>
      {label}
      <select
        className="h-10 rounded-control border border-line bg-surface px-3 text-ink outline-none focus:border-primary"
        id={id}
        onChange={(event) => onChange(id, event.target.value)}
        value={value}
      >
        <option value="">Não informado</option>
        {options.map(([option, title]) => (
          <option key={option} value={option}>
            {title}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function PacientesPage() {
  const [values, setValues] = useState<AssessmentValues>(INITIAL_VALUES);
  const [protocol, setProtocol] = useState<number | null>(null);
  const assessment = useMutation({
    mutationFn: (submission: AssessmentForm) =>
      apiPost<Schemas["PatientAssessmentCreated"]>("/api/pacientes/avaliacao", submission),
    onSuccess: (result) => {
      setProtocol(result.intake_id);
      setValues(INITIAL_VALUES);
    },
  });

  const updateField = (field: keyof AssessmentForm, value: string) => {
    setProtocol(null);
    assessment.reset();
    setValues((current) => ({ ...current, [field]: value }));
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const submission: AssessmentForm = {
      age_group: values.age_group || null,
      sex: values.sex || null,
      symptom_duration: values.symptom_duration || null,
      fever: values.fever || null,
      headache: values.headache || null,
      muscle_pain: values.muscle_pain || null,
      rash: values.rash || null,
      nausea: values.nausea || null,
      vomiting: values.vomiting || null,
      pregnancy: values.pregnancy || null,
      comorbidities: values.comorbidities || null,
    };
    assessment.mutate(submission);
  };

  return (
    <>
      <PageHeader
        titulo="Formulário de acolhimento"
        descricao="Registre as informações iniciais para avaliação de completude pela equipe no Oracle APEX."
      />

      <IntegrationNotice titulo="Registro sem identificação direta">
        <p>
          Não informe nome, CPF, endereço, telefone ou texto livre. Os campos não preenchidos serão gravados
          como pendentes para que a equipe analise a completude no APEX. Este formulário não diagnostica nem
          determina prioridade de atendimento.
        </p>
      </IntegrationNotice>

      <Panel
        titulo="Informações iniciais"
        subtitulo="Preencha o que foi informado no acolhimento; deixe como “Não informado” quando não souber."
        className="mx-auto w-full max-w-4xl"
      >
        <form className="flex flex-col gap-6" onSubmit={submit}>
          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="mb-3 text-sm font-semibold text-ink">Dados gerais</legend>
            <SelectField
              id="age_group"
              label="Faixa etária"
              options={OPCOES_IDADE}
              value={values.age_group}
              onChange={updateField}
            />
            <SelectField
              id="sex"
              label="Sexo informado"
              options={[
                ["F", "Feminino"],
                ["M", "Masculino"],
                ["OUTRO", "Outro"],
              ]}
              value={values.sex}
              onChange={updateField}
            />
            <SelectField
              id="symptom_duration"
              label="Quando os sintomas começaram?"
              options={[
                ["HOJE", "Hoje"],
                ["1-3_DIAS", "Há 1 a 3 dias"],
                ["4+_DIAS", "Há 4 dias ou mais"],
              ]}
              value={values.symptom_duration}
              onChange={updateField}
            />
          </fieldset>

          <fieldset className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <legend className="mb-3 text-sm font-semibold text-ink">Sintomas relatados</legend>
            {CAMPOS_SINTOMAS.map(({ chave, rotulo }) => (
              <SelectField
                id={chave}
                key={chave}
                label={rotulo}
                options={OPCOES_SIM_NAO}
                value={values[chave]}
                onChange={updateField}
              />
            ))}
          </fieldset>

          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="mb-3 text-sm font-semibold text-ink">Informações adicionais</legend>
            <SelectField
              id="pregnancy"
              label="Gestação informada"
              options={OPCOES_SIM_NAO}
              value={values.pregnancy}
              onChange={updateField}
            />
            <SelectField
              id="comorbidities"
              label="Comorbidades informadas"
              options={OPCOES_SIM_NAO}
              value={values.comorbidities}
              onChange={updateField}
            />
          </fieldset>

          {assessment.isError && (
            <p className="text-sm text-danger" role="alert">
              Não foi possível registrar as informações. Verifique se a API está conectada ao Oracle e tente
              novamente.
            </p>
          )}
          {protocol !== null && (
            <p className="flex items-center gap-2 rounded-control bg-primary-soft px-3 py-2 text-sm text-primary-ink" role="status">
              <CheckCircle2 aria-hidden className="size-4 shrink-0" />
              Registro {protocol} enviado à fila de avaliação do APEX.
            </p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="max-w-xl text-xs leading-5 text-muted">
              Campos não informados serão sinalizados na fila do APEX. O registro ficará pendente de avaliação
              por um analista.
            </p>
            <Button variante="primario" type="submit" disabled={assessment.isPending}>
              <Send aria-hidden className="size-3.5" />
              {assessment.isPending ? "Enviando..." : "Enviar para avaliação"}
            </Button>
          </div>
        </form>
      </Panel>
    </>
  );
}
