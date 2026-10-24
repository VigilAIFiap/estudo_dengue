"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { useMemo, useState, useEffect } from "react";
import { GlobalFilters } from "@/components/filters/global-filters";
import { BrazilMap, ROTULO_CAMADA, useEscala, type Camada } from "@/components/map/brazil-map";
import { MapLegend } from "@/components/map/map-legend";
import { PageHeader } from "@/components/shell/page-header";
import { useHrefComFiltros } from "@/components/shell/app-sidebar";
import { CriticalityBadge } from "@/components/ui/criticality-badge";
import { cn } from "@/components/ui/cn";
import { Panel } from "@/components/ui/panel";
import { Segmented } from "@/components/ui/segmented";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { Schemas } from "@/lib/api";
import { inicialMaiuscula, useRotuloBase } from "@/lib/base-municipal";
import { fmtDec, fmtInt, fmtPct } from "@/lib/format";
import { useMapa, useMeta, useMunicipio } from "@/lib/queries";
import { useFiltros, useParametro } from "@/lib/use-filtros";

const CAMADAS: Camada[] = ["notificacoes", "confirmados", "hospitalizacoes", "obitos", "score"];

export default function MapaPage() {
  const mapa = useMapa();
  const meta = useMeta();
  const rotuloBase = useRotuloBase();
  const { filtros } = useFiltros();
  const [camadaParam, setCamada] = useParametro("camada");
  const [selParam, setSel] = useParametro("sel");
  const camada = (CAMADAS.includes(camadaParam as Camada) ? camadaParam : "notificacoes") as Camada;
  const selecionado = selParam ? Number(selParam) : (filtros.municipio ?? null);
  const pontos = useMemo(() => mapa.data?.pontos ?? [], [mapa.data]);
  const { cortes } = useEscala(pontos, camada);
  const altura = useAlturaMapa();

  return (
    <>
      <PageHeader
        titulo="Inteligência geográfica"
        descricao={`Limites municipais do IBGE coloridos pelo indicador escolhido, por ${rotuloBase}. Arraste para mover, use a roda do mouse ou os botões para aproximar e clique em um município para ver os detalhes.`}
      />
      <GlobalFilters ignorados={{ municipio: "No mapa, o município filtrado fica destacado e os demais continuam visíveis." }} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Panel
          id="mapa"
          className="xl:col-span-8"
          titulo={ROTULO_CAMADA[camada]}
          subtitulo={
            camada === "score"
              ? "Nível do score de criticidade do projeto, relativo aos municípios do recorte"
              : `Total no período, por ${rotuloBase}`
          }
          corpoClassName="flex flex-col gap-3"
        >
          <div className="overflow-x-auto">
            <Segmented
              rotulo="Camada do mapa"
              valor={camada}
              onChange={(v) => setCamada(v === "notificacoes" ? null : v)}
              opcoes={CAMADAS.map((c) => ({ valor: c, rotulo: c === "score" ? "Criticidade" : ROTULO_CAMADA[c] }))}
            />
          </div>
          {mapa.isError ? (
            <ErrorState erro={mapa.error} tentarNovamente={() => mapa.refetch()} />
          ) : !mapa.data ? (
            <LoadingState altura={altura} rotulo="Carregando mapa" />
          ) : (
            <BrazilMap
              pontos={pontos}
              camada={camada}
              selecionado={selecionado}
              onSelecionar={(id) => setSel(id ? String(id) : null)}
              ufFoco={filtros.uf}
              altura={altura}
            />
          )}
          <MapLegend
            camada={camada}
            cortes={cortes}
            contagens={
              mapa.data
                ? {
                    semNotificacao: mapa.data.sem_notificacao,
                    semScore: mapa.data.sem_score,
                    q1: mapa.data.q1,
                    base: meta.data?.base_municipal ?? "notificacao",
                    semResidencia: meta.data?.sem_residencia ?? 0,
                  }
                : undefined
            }
          />
          <p className="text-xs leading-5 text-muted">
            Malha municipal: IBGE via geodata-br (CC0), simplificada para exibição. Não há população na base, por isso o mapa mostra
            contagens absolutas e não incidência por 100 mil habitantes.
          </p>
        </Panel>

        <div className="flex flex-col gap-5 xl:col-span-4">
          {selecionado ? (
            <DetalheSelecionado id={selecionado} onFechar={() => setSel(null)} />
          ) : (
            <ResumoUf ufs={mapa.data?.ufs} />
          )}
          <Panel id="lista" titulo="Ranking sincronizado" subtitulo={`15 maiores valores de ${ROTULO_CAMADA[camada].toLowerCase()}`}>
            {!mapa.data ? (
              <LoadingState altura={300} />
            ) : (
              <ListaCamada pontos={pontos} camada={camada} selecionado={selecionado} onEscolher={(id) => setSel(String(id))} />
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}

function useAlturaMapa() {
  const [altura, setAltura] = useState(620);
  useEffect(() => {
    const atualizar = () => setAltura(window.innerWidth < 640 ? 380 : window.innerWidth < 1280 ? 520 : 640);
    atualizar();
    window.addEventListener("resize", atualizar);
    return () => window.removeEventListener("resize", atualizar);
  }, []);
  return altura;
}

function ListaCamada({
  pontos,
  camada,
  selecionado,
  onEscolher,
}: {
  pontos: Schemas["PontoMapa"][];
  camada: Camada;
  selecionado: number | null;
  onEscolher: (id: number) => void;
}) {
  const valor = (p: Schemas["PontoMapa"]) => (camada === "score" ? (p.score ?? -1) : p[camada]);
  const topo = [...pontos].sort((a, b) => valor(b) - valor(a)).slice(0, 15);
  return (
    <ol className="flex flex-col">
      {topo.map((p, i) => (
        <li key={p.id}>
          <button
            type="button"
            onClick={() => onEscolher(p.id)}
            aria-pressed={selecionado === p.id}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-1.5 py-1.5 text-left text-[13px] hover:bg-canvas",
              selecionado === p.id && "bg-primary-soft hover:bg-primary-soft",
            )}
          >
            <span className="num w-5 text-right text-xs text-faint">{i + 1}</span>
            <span className="min-w-0 flex-1 truncate text-ink">
              {p.nome} <span className="text-xs text-muted">{p.uf}</span>
            </span>
            {camada === "score" && <CriticalityBadge nivel={p.nivel} compacto />}
            <span className="num w-16 text-right font-medium text-ink">
              {camada === "score" ? (p.score == null ? "—" : fmtDec(p.score)) : fmtInt(p[camada])}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function ResumoUf({ ufs }: { ufs: Schemas["UfMapa"][] | undefined }) {
  return (
    <Panel id="uf" titulo="Por unidade da federação" subtitulo="Clique em um município no mapa para ver o detalhe">
      {!ufs ? (
        <LoadingState altura={240} />
      ) : (
        <div className="max-h-[300px] overflow-auto">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Totais por UF</caption>
            <thead className="sticky top-0 bg-surface text-xs text-muted">
              <tr>
                <th scope="col" className="py-1.5 text-left font-normal">UF</th>
                <th scope="col" className="py-1.5 text-right font-normal">Notificações</th>
                <th scope="col" className="py-1.5 text-right font-normal">Óbitos</th>
                <th scope="col" className="py-1.5 text-right font-normal">Críticos</th>
              </tr>
            </thead>
            <tbody>
              {[...ufs]
                .sort((a, b) => b.notificacoes - a.notificacoes)
                .map((u) => (
                  <tr key={u.uf} className="border-t border-line">
                    <th scope="row" className="py-1.5 text-left font-normal text-ink">
                      {u.nome}
                    </th>
                    <td className="num py-1.5 text-right text-ink">{fmtInt(u.notificacoes)}</td>
                    <td className="num py-1.5 text-right text-ink-2">{fmtInt(u.obitos)}</td>
                    <td className="num py-1.5 text-right text-ink-2">{fmtInt(u.criticos)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function DetalheSelecionado({ id, onFechar }: { id: number; onFechar: () => void }) {
  const d = useMunicipio(id);
  const rotuloBase = useRotuloBase();
  const href = useHrefComFiltros();
  return (
    <Panel
      id="selecionado"
      titulo={d.data ? `${d.data.nome} (${d.data.uf})` : "Município selecionado"}
      subtitulo={d.data?.capital ? "Capital" : inicialMaiuscula(rotuloBase)}
      acoes={
        <button type="button" onClick={onFechar} aria-label="Fechar detalhe" className="rounded-md p-1 text-muted hover:bg-sunken">
          <X aria-hidden className="size-4" />
        </button>
      }
      rodape={
        d.data && (
          <Link
            href={`${href("/municipios")}${href("/municipios").includes("?") ? "&" : "?"}m=${id}`}
            className="font-medium text-primary-ink hover:underline"
          >
            Abrir análise do município
          </Link>
        )
      }
    >
      {d.isError ? (
        <ErrorState erro={d.error} />
      ) : !d.data ? (
        <LoadingState altura={200} />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <CriticalityBadge nivel={d.data.nivel} />
            <span className="text-[13px] text-muted">
              Score <span className="num font-semibold text-ink">{d.data.score == null ? "—" : fmtDec(d.data.score)}</span>
              {d.data.posicao && <> ({d.data.posicao}º de {fmtInt(d.data.municipios_pontuados)})</>}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
            {[
              ["Notificações", fmtInt(d.data.notificacoes)],
              ["Confirmados", fmtInt(d.data.confirmados)],
              ["Alarme ou grave", fmtInt(d.data.graves)],
              ["Óbitos pelo agravo", fmtInt(d.data.obitos_dengue)],
              ["Hospitalizações", fmtInt(d.data.hospitalizacoes)],
              ["Taxa de hospitalização", fmtPct(d.data.taxa_hospitalizacao)],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="num text-[17px] font-semibold text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </Panel>
  );
}
