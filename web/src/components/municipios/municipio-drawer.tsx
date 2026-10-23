"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { EpiCurve } from "@/components/charts/epi-curve";
import { CriticalityBadge } from "@/components/ui/criticality-badge";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { fmtDec, fmtInt, fmtPct } from "@/lib/format";
import { useMunicipio } from "@/lib/queries";

function BarraComponente({ rotulo, valor, cor, detalhe }: { rotulo: string; valor: number; cor: string; detalhe?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs text-ink-2">
        <span className="font-medium">{rotulo}</span>
        <span className="num">{fmtDec(valor)}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-sunken" aria-hidden>
        <span className="block h-full rounded-full" style={{ width: `${valor}%`, background: cor }} />
      </div>
      {detalhe && <p className="mt-1 text-xs text-muted">{detalhe}</p>}
    </div>
  );
}

export function MunicipioDrawer({ id, onFechar }: { id: number | null; onFechar: () => void }) {
  const d = useMunicipio(id);
  const m = d.data;
  return (
    <Dialog.Root open={!!id} onOpenChange={(a) => !a && onFechar()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/25" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] flex-col bg-surface shadow-float focus:outline-none">
          <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-ink">{m ? m.nome : "Carregando município"}</Dialog.Title>
              <Dialog.Description className="text-[13px] text-muted">
                {m ? `${m.uf}${m.capital ? ", capital" : ""}. Código IBGE ${m.id_municip}.` : "Indicadores no recorte selecionado"}
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Fechar" className="rounded-md p-1.5 text-muted hover:bg-sunken">
              <X aria-hidden className="size-5" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {d.isError ? (
              <ErrorState erro={d.error} tentarNovamente={() => d.refetch()} />
            ) : !m ? (
              <LoadingState altura={400} />
            ) : (
              <div className="flex flex-col gap-6">
                <section aria-label="Score de criticidade" className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <CriticalityBadge nivel={m.nivel} />
                    <p className="text-[13px] text-muted">
                      {m.posicao ? `${m.posicao}º de ${fmtInt(m.municipios_pontuados)} municípios pontuados` : "Volume abaixo do 1º quartil: sem score"}
                    </p>
                  </div>
                  <p className="num text-kpi font-semibold text-ink">
                    {m.score == null ? "—" : fmtDec(m.score)}
                    <span className="ml-1 text-sm font-normal text-muted">de 100</span>
                  </p>
                  {m.componentes && (
                    <div className="flex flex-col gap-2.5">
                      <BarraComponente rotulo="Fator de volume" valor={m.componentes.volume} cor="#2563eb" />
                      <BarraComponente
                        rotulo="Severidade"
                        valor={m.componentes.severidade}
                        cor="#dc2626"
                        detalhe={`Óbito: percentil ${fmtDec(m.componentes.obito)} · Hospitalização: percentil ${fmtDec(m.componentes.hospitalizacao)}`}
                      />
                      <p className="text-xs text-muted">Score = volume × severidade.</p>
                      {m.componentes.taxas_suavizadas && (
                        <p className="text-xs text-muted">Poucas notificações: as taxas foram suavizadas em direção à média do recorte.</p>
                      )}
                    </div>
                  )}
                </section>

                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                  {[
                    ["Notificações", fmtInt(m.notificacoes)],
                    ["Confirmados", fmtInt(m.confirmados)],
                    ["Alarme ou grave", fmtInt(m.graves)],
                    ["Óbitos pelo agravo", fmtInt(m.obitos_dengue)],
                    ["Hospitalizações", fmtInt(m.hospitalizacoes)],
                    ["Taxa de hospitalização", fmtPct(m.taxa_hospitalizacao)],
                    ["Letalidade entre confirmados", fmtPct(m.letalidade, 2)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs text-muted">{k}</dt>
                      <dd className="num text-lg font-semibold text-ink">{v}</dd>
                    </div>
                  ))}
                </dl>

                <section aria-labelledby="curva-mun">
                  <h3 id="curva-mun" className="mb-2 text-sm font-semibold text-ink">
                    Notificações por semana epidemiológica
                  </h3>
                  <EpiCurve serie={m.serie} altura={220} />
                </section>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
