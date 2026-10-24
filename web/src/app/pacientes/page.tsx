"use client";

import { useMutation } from "@tanstack/react-query";
import { Send, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ChoiceGroup, type Opcao } from "@/components/acolhimento/choice-group";
import { FluxoValidacao } from "@/components/acolhimento/fluxo-validacao";
import { PreviaValidacao } from "@/components/acolhimento/previa-validacao";
import { ResultadoTriagem } from "@/components/acolhimento/resultado-triagem";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { ApiError, apiPost, type Schemas } from "@/lib/api";
import {
  VALORES_INICIAIS,
  gestacaoSeAplica,
  paraEnvio,
  validarTriagem,
  type CampoTriagem,
  type ValoresTriagem,
} from "@/lib/triagem";

const APEX_URL = process.env.NEXT_PUBLIC_APEX_URL || undefined;

const NAO_INFORMADO: Opcao = { valor: "", rotulo: "Não informado" };
const SIM_NAO: Opcao[] = [
  { valor: "SIM", rotulo: "Sim" },
  { valor: "NAO", rotulo: "Não" },
  NAO_INFORMADO,
];
const IDADES: Opcao[] = [
  { valor: "0-4", rotulo: "0 a 4" },
  { valor: "5-9", rotulo: "5 a 9" },
  { valor: "10-19", rotulo: "10 a 19" },
  { valor: "20-39", rotulo: "20 a 39" },
  { valor: "40-59", rotulo: "40 a 59" },
  { valor: "60+", rotulo: "60 ou mais" },
  NAO_INFORMADO,
];
const SEXOS: Opcao[] = [
  { valor: "F", rotulo: "Feminino" },
  { valor: "M", rotulo: "Masculino" },
  { valor: "OUTRO", rotulo: "Outro" },
  NAO_INFORMADO,
];
const INICIO: Opcao[] = [
  { valor: "HOJE", rotulo: "Hoje" },
  { valor: "1-3_DIAS", rotulo: "Há 1 a 3 dias" },
  { valor: "4+_DIAS", rotulo: "Há 4 dias ou mais" },
  NAO_INFORMADO,
];
const SINTOMAS: { campo: CampoTriagem; rotulo: string }[] = [
  { campo: "fever", rotulo: "Febre" },
  { campo: "headache", rotulo: "Dor de cabeça" },
  { campo: "muscle_pain", rotulo: "Dor muscular" },
  { campo: "rash", rotulo: "Manchas ou erupção na pele" },
  { campo: "nausea", rotulo: "Náusea" },
  { campo: "vomiting", rotulo: "Vômito" },
];

function detalheDoErro(erro: unknown): string {
  // 503 (formulário desativado) e 403 (origem não permitida) trazem uma mensagem própria da API.
  if (erro instanceof ApiError && (erro.status === 503 || erro.status === 403)) return erro.message;
  return "Verifique se a API está conectada ao Oracle e tente novamente.";
}

function Etapa({ numero, titulo, children }: { numero: number; titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4 border-t border-line pt-5 first:border-t-0 first:pt-0">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <span className="flex size-5 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary-ink">
          {numero}
        </span>
        {titulo}
      </h3>
      {children}
    </section>
  );
}

export default function PacientesPage() {
  const [valores, setValores] = useState<ValoresTriagem>(VALORES_INICIAIS);
  const [resultado, setResultado] = useState<Schemas["PatientAssessmentCreated"] | null>(null);
  const envio = useMutation({
    mutationFn: (corpo: Schemas["PatientAssessmentSubmission"]) =>
      apiPost<Schemas["PatientAssessmentCreated"]>("/api/pacientes/avaliacao", corpo),
    onSuccess: (resposta) => {
      setResultado(resposta);
      setValores(VALORES_INICIAIS);
    },
  });

  const mudar = (campo: CampoTriagem, valor: string) => {
    setResultado(null);
    envio.reset();
    setValores((atual) => ({ ...atual, [campo]: valor }));
  };

  const enviar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    envio.mutate(paraEnvio(valores));
  };

  const validacao = validarTriagem(valores);
  const gestacaoAplica = gestacaoSeAplica(valores);

  return (
    <>
      <PageHeader
        titulo="Acolhimento"
        descricao="Triagem com validação automática no Oracle. Registros sem erros são aprovados na hora; os demais vão para revisão no Oracle APEX."
      />

      <p className="mb-5 flex items-start gap-2 rounded-control border border-teal/30 bg-teal-soft px-3.5 py-2.5 text-[13px] leading-5 text-ink-2">
        <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-teal" />
        <span>
          <strong className="font-semibold text-ink">Modo demonstração:</strong> use apenas dados fictícios. O formulário
          não coleta nome, documento, endereço nem texto livre, e não diagnostica nem define prioridade de atendimento.
        </span>
      </p>

      <FluxoValidacao />

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-12">
        <form className="lg:col-span-8" onSubmit={enviar}>
          <Panel
            id="triagem"
            titulo="Dados da triagem"
            subtitulo="Preencha o que foi informado no atendimento; use “Não informado” quando não souber."
            destaque="primary"
            corpoClassName="flex flex-col gap-5"
          >
            <Etapa numero={1} titulo="Perfil">
              <div className="grid gap-4 sm:grid-cols-2">
                <ChoiceGroup campo="age_group" legenda="Faixa etária" dica="Em anos" opcoes={IDADES} valor={valores.age_group} aoMudar={mudar} />
                <ChoiceGroup campo="sex" legenda="Sexo informado" opcoes={SEXOS} valor={valores.sex} aoMudar={mudar} />
              </div>
            </Etapa>

            <Etapa numero={2} titulo="Sintomas">
              <ChoiceGroup campo="symptom_duration" legenda="Início dos sintomas" opcoes={INICIO} valor={valores.symptom_duration} aoMudar={mudar} />
              <div className="grid gap-4 sm:grid-cols-2">
                {SINTOMAS.map(({ campo, rotulo }) => (
                  <ChoiceGroup key={campo} campo={campo} legenda={rotulo} opcoes={SIM_NAO} valor={valores[campo]} aoMudar={mudar} />
                ))}
              </div>
            </Etapa>

            <Etapa numero={3} titulo="Condições de saúde">
              <div className="grid gap-4 sm:grid-cols-2">
                <ChoiceGroup
                  campo="pregnancy"
                  legenda="Gestação"
                  dica={gestacaoAplica ? undefined : "Não se aplica ao sexo masculino nem à faixa de 0 a 9 anos."}
                  opcoes={SIM_NAO}
                  valor={valores.pregnancy}
                  aoMudar={mudar}
                />
                <ChoiceGroup campo="comorbidities" legenda="Comorbidades" opcoes={SIM_NAO} valor={valores.comorbidities} aoMudar={mudar} />
              </div>
            </Etapa>

            {envio.isError && (
              <p className="rounded-control border border-critico/25 bg-critico-soft px-3 py-2 text-sm text-critico-ink" role="alert">
                Não foi possível registrar as informações. {detalheDoErro(envio.error)}
              </p>
            )}
            {resultado && <ResultadoTriagem resultado={resultado} apexUrl={APEX_URL} />}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
              <p className="max-w-md text-xs leading-5 text-muted">
                Campos não informados e combinações inconsistentes não bloqueiam o envio: o registro segue para revisão.
              </p>
              <Button variante="primario" type="submit" disabled={envio.isPending} className="h-10 px-5 text-sm">
                <Send aria-hidden className="size-3.5" />
                {envio.isPending ? "Enviando..." : "Enviar triagem"}
              </Button>
            </div>
          </Panel>
        </form>

        <aside className="lg:col-span-4">
          <div className="lg:sticky lg:top-20">
            <PreviaValidacao resultado={validacao} />
          </div>
        </aside>
      </div>
    </>
  );
}
