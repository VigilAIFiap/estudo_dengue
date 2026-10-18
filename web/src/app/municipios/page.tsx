"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useState } from "react";
import type { SortingState } from "@tanstack/react-table";
import { GlobalFilters } from "@/components/filters/global-filters";
import { Comparison } from "@/components/municipios/comparison";
import { Methodology } from "@/components/municipios/methodology";
import { MunicipioDrawer } from "@/components/municipios/municipio-drawer";
import { MunicipalityTable } from "@/components/municipios/municipality-table";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { ExportButton } from "@/components/ui/export-button";
import { MultiSelect } from "@/components/ui/multi-select";
import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { NIVEIS } from "@/lib/criticality";
import { fmtInt } from "@/lib/format";
import { urlExportacao, useFiltrosResolvidos, useRanking } from "@/lib/queries";
import { useDebounce } from "@/lib/use-debounce";
import { useDefinirParametros, useFiltros, useParametro } from "@/lib/use-filtros";

const LIMITE_COMPARACAO = 4;
const TAMANHOS = [25, 50, 100];

export default function MunicipiosPage() {
  const { params } = useFiltrosResolvidos();
  const { filtros } = useFiltros();
  const [aberto, setAberto] = useParametro("m");
  const [compararParam, setComparar] = useParametro("comparar");
  const [ordParam] = useParametro("ordem");
  const [paginaParam, setPagina] = useParametro("pagina");
  const [nivelParam] = useParametro("nivel");
  const [busca, setBusca] = useState("");
  const buscaAtrasada = useDebounce(busca, 300);
  const [tamanho, setTamanho] = useState(25);
  const definirParams = useDefinirParametros();

  const [coluna = "score_criticidade", direcao = "desc"] = (ordParam ?? "").split(":").filter(Boolean);
  const ordenacao: SortingState = [{ id: coluna, desc: direcao !== "asc" }];
  const pagina = Math.max(1, Number(paginaParam) || 1);
  const niveis = nivelParam ? nivelParam.split(",").filter((n) => (NIVEIS as readonly string[]).includes(n)) : [];
  const comparar = compararParam ? compararParam.split(",").map(Number).filter(Boolean).slice(0, LIMITE_COMPARACAO) : [];

  useEffect(() => {
    // Busca nova volta para a primeira página.
    if (buscaAtrasada) setPagina(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAtrasada]);

  const ranking = useRanking({
    pagina,
    tamanho,
    ordenar: coluna,
    direcao: direcao === "asc" ? "asc" : "desc",
    busca: buscaAtrasada,
    nivel: niveis,
  });
  const r = ranking.data;
  const totalPaginas = r ? Math.max(1, Math.ceil(r.total / r.tamanho)) : 1;

  const alternar = (id: number) => {
    const proximo = comparar.includes(id) ? comparar.filter((c) => c !== id) : [...comparar, id];
    setComparar(proximo.length ? proximo.join(",") : null);
  };

  return (
    <>
      <PageHeader
        titulo="Ranking e análise de municípios"
        descricao="Indicadores por município notificador e o score de criticidade do projeto. Marque até quatro municípios para comparar."
        acoes={<ExportButton href={urlExportacao("/api/export/municipios.csv", params)}>Exportar ranking</ExportButton>}
      />
      <GlobalFilters ignorados={{ municipio: "O ranking mostra todos os municípios; o filtrado aparece destacado." }} />

      {comparar.length > 0 && (
        <div className="mb-5">
          {comparar.length === 1 ? (
            <p className="rounded-control border border-dashed border-line-strong px-4 py-3 text-[13px] text-muted">
              Marque mais um município na tabela para comparar.
            </p>
          ) : (
            <Comparison ids={comparar} onRemover={alternar} onLimpar={() => setComparar(null)} />
          )}
        </div>
      )}

      <Panel
        id="tabela"
        titulo="Municípios"
        subtitulo={r ? `${fmtInt(r.total)} municípios com notificações no recorte` : "Carregando"}
        corpoClassName="flex flex-col gap-3"
      >
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex h-8 w-full items-center gap-2 rounded-control border border-line bg-surface px-2.5 sm:w-64">
            <Search aria-hidden className="size-3.5 text-faint" />
            <span className="sr-only">Buscar por nome</span>
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por nome"
              className="w-full bg-transparent text-[13px] outline-none placeholder:text-faint"
            />
          </label>
          <MultiSelect
            rotulo="Nível"
            opcoes={NIVEIS.map((n) => ({ valor: n, rotulo: n }))}
            selecionados={niveis}
            onChange={(n) => definirParams({ nivel: n.length ? n.join(",") : null, pagina: null })}
            resumo={niveis.length ? niveis.join(", ") : "Todos"}
          />
        </div>

        {ranking.isError ? (
          <ErrorState erro={ranking.error} tentarNovamente={() => ranking.refetch()} />
        ) : !r ? (
          <LoadingState altura={480} />
        ) : !r.itens.length ? (
          <EmptyState titulo="Nenhum município encontrado">Revise a busca ou o filtro de nível.</EmptyState>
        ) : (
          <MunicipalityTable
            itens={r.itens}
            ordenacao={ordenacao}
            onOrdenar={(s) => {
              const o = s[0];
              definirParams({
                ordem: o && !(o.id === "score_criticidade" && o.desc) ? `${o.id}:${o.desc ? "desc" : "asc"}` : null,
                pagina: null,
              });
            }}
            selecionados={comparar}
            onAlternarSelecao={alternar}
            onAbrir={(id) => setAberto(String(id))}
            destaque={filtros.municipio}
            carregando={ranking.isFetching}
            limiteSelecao={LIMITE_COMPARACAO}
          />
        )}

        {r && r.total > 0 && (
          <nav aria-label="Paginação" className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-muted">
            <span className="num">
              {fmtInt((r.pagina - 1) * r.tamanho + 1)}–{fmtInt(Math.min(r.pagina * r.tamanho, r.total))} de {fmtInt(r.total)}
            </span>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5">
                Por página
                <select
                  value={tamanho}
                  onChange={(e) => {
                    setTamanho(Number(e.target.value));
                    setPagina(null);
                  }}
                  className="h-8 rounded-control border border-line bg-surface px-1.5 text-ink"
                >
                  {TAMANHOS.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </label>
              <Button aria-label="Página anterior" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1 <= 1 ? null : String(pagina - 1))}>
                <ChevronLeft aria-hidden className="size-4" />
              </Button>
              <span className="num">
                {pagina} / {totalPaginas}
              </span>
              <Button aria-label="Próxima página" disabled={pagina >= totalPaginas} onClick={() => setPagina(String(pagina + 1))}>
                <ChevronRight aria-hidden className="size-4" />
              </Button>
            </div>
          </nav>
        )}
      </Panel>

      <div className="mt-5">
        <Panel id="metodologia" titulo="Metodologia do score de criticidade">
          {r ? <Methodology m={r.metodologia} /> : <LoadingState altura={160} />}
        </Panel>
      </div>

      <MunicipioDrawer id={aberto ? Number(aberto) : null} onFechar={() => setAberto(null)} />
    </>
  );
}
