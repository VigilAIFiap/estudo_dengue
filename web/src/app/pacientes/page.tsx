"use client";

import { ShieldAlert } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { IntegrationNotice } from "@/components/ui/integration-notice";
import { Panel } from "@/components/ui/panel";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { usePacientesStatus } from "@/lib/queries";

export default function PacientesPage() {
  const status = usePacientesStatus();
  const s = status.data;

  return (
    <>
      <PageHeader
        titulo="Assistente de análise de pacientes"
        descricao="Interface para os classificadores experimentais de src/modelos/pacientes.py: probabilidade de dengue confirmada e escore de hospitalização entre confirmados."
      />
      {status.isError ? (
        <ErrorState erro={status.error} tentarNovamente={() => status.refetch()} />
      ) : !s ? (
        <LoadingState altura={200} />
      ) : s.disponivel ? (
        <IntegrationNotice titulo="Colunas clínicas disponíveis, mas o serviço de inferência não está exposto">
          <p>A base tem as colunas exigidas. Falta publicar o modelo treinado em uma rota autenticada antes de habilitar o formulário.</p>
        </IntegrationNotice>
      ) : (
        <IntegrationNotice titulo="Em desenvolvimento: a base carregada não tem dados clínicos">
          <p>
            Os modelos precisam de sintomas, comorbidades, idade, sexo e gestação. Os CSVs atuais têm só{" "}
            <span className="font-medium text-ink">{s.colunas_disponiveis.join(", ")}</span>. Nenhum resultado é simulado.
          </p>
        </IntegrationNotice>
      )}

      {s && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Panel titulo="Colunas que faltam" subtitulo={`${s.colunas_faltando.length} campos exigidos pelo modelo`}>
            <ul className="flex flex-wrap gap-1.5">
              {s.colunas_faltando.map((c) => (
                <li key={c} className="rounded-chip bg-sunken px-2 py-0.5 text-xs text-ink-2">
                  {c}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[13px] leading-5 text-muted">
              Esses campos existem na Bronze completa do Oracle (DENGBR25/26). Regenerar a camada Prata com src/etl.py a partir dela habilita o
              treino.
            </p>
          </Panel>
          <Panel titulo="Antes de habilitar o formulário">
            <ul className="flex flex-col gap-2.5 text-[13px] leading-5 text-ink-2">
              {[
                "Finalidade definida e base legal para tratar dados de saúde (LGPD, art. 11), com coleta mínima.",
                "Acesso autenticado e registro de quem consultou o quê; nada de dados pessoais no navegador além do necessário.",
                "Validação clínica dos modelos com dados representativos; hoje há só métricas de validação temporal sobre notificações.",
                "Resultados descritos como escores experimentais, sem diagnóstico, sem recomendação de tratamento.",
              ].map((t) => (
                <li key={t} className="flex gap-2.5">
                  <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-faint" />
                  {t}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      )}
    </>
  );
}
