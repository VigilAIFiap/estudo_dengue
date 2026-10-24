"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiGet, type Schemas } from "./api";
import { paraParametros, type Filtros } from "./filters";
import { useFiltros } from "./use-filtros";

export function useMeta() {
  return useQuery({
    queryKey: ["meta"],
    queryFn: ({ signal }) => apiGet<Schemas["Meta"]>("/api/meta", undefined, signal),
    staleTime: Infinity,
  });
}

/** Filtros da URL resolvidos com o período padrão informado pela API. */
export function useFiltrosResolvidos() {
  const { filtros } = useFiltros();
  const meta = useMeta();
  const padrao = meta.data ? { inicio: meta.data.padrao_inicio, fim: meta.data.padrao_fim } : undefined;
  const params = paraParametros(filtros, padrao);
  return {
    filtros,
    meta,
    params,
    chave: params.toString(),
    inicio: filtros.inicio ?? padrao?.inicio,
    fim: filtros.fim ?? padrao?.fim,
    pronto: meta.isSuccess,
  };
}

type Extra = Record<string, string | string[] | number | undefined>;

function useConsulta<T>(nome: string, caminho: string, extra?: Extra, opcoes?: { substituir?: Extra; ativo?: boolean }) {
  const { params, chave, pronto } = useFiltrosResolvidos();
  const p = new URLSearchParams(params);
  for (const [k, v] of Object.entries(opcoes?.substituir ?? {})) {
    p.delete(k);
    if (v != null) p.set(k, String(v));
  }
  for (const [k, v] of Object.entries(extra ?? {})) {
    if (v == null) continue;
    for (const item of Array.isArray(v) ? v : [String(v)]) p.append(k, item);
  }
  return useQuery({
    queryKey: [nome, caminho, chave, p.toString()],
    queryFn: ({ signal }) => apiGet<T>(caminho, p, signal),
    enabled: pronto && (opcoes?.ativo ?? true),
    placeholderData: keepPreviousData,
  });
}

export const useVisaoGeral = () => useConsulta<Schemas["VisaoGeral"]>("visao", "/api/visao-geral");
export const useSeries = (granularidade: "semana" | "mes") =>
  useConsulta<Schemas["PontoSerie"][]>("series", "/api/series", { granularidade });
/** A mesma série em outro intervalo (ex.: mesmas semanas do ano anterior). */
export const useSeriesEm = (granularidade: "semana" | "mes", intervalo: { inicio: string; fim: string } | null | undefined) =>
  useConsulta<Schemas["PontoSerie"][]>(
    "series",
    "/api/series",
    { granularidade },
    { substituir: { inicio: intervalo?.inicio, fim: intervalo?.fim }, ativo: !!intervalo },
  );
export const useDistribuicoes = () => useConsulta<Schemas["Distribuicoes"]>("dist", "/api/distribuicoes");
export const useMapa = () => useConsulta<Schemas["Mapa"]>("mapa", "/api/mapa");
export const usePrevisao = () => useConsulta<Schemas["Previsao"]>("previsao", "/api/previsao");

export type EstadoTabela = {
  pagina: number;
  tamanho: number;
  ordenar: string;
  direcao: "asc" | "desc";
  busca?: string;
  nivel: string[];
};

export const useRanking = (t: EstadoTabela) =>
  useConsulta<Schemas["Ranking"]>("ranking", "/api/municipios", {
    pagina: t.pagina,
    tamanho: t.tamanho,
    ordenar: t.ordenar,
    direcao: t.direcao,
    busca: t.busca || undefined,
    nivel: t.nivel,
  });

export function useMunicipio(id: number | null | undefined) {
  const { params, chave, pronto } = useFiltrosResolvidos();
  const p = new URLSearchParams(params);
  p.delete("municipio");
  return useQuery({
    queryKey: ["municipio", id, chave],
    queryFn: ({ signal }) => apiGet<Schemas["DetalheMunicipio"]>(`/api/municipios/${id}`, p, signal),
    enabled: pronto && !!id,
    placeholderData: keepPreviousData,
  });
}

export function useBuscaMunicipios(termo: string) {
  const q = termo.trim();
  return useQuery({
    queryKey: ["busca", q],
    queryFn: ({ signal }) =>
      apiGet<Schemas["MunicipioBusca"][]>("/api/municipios/busca", new URLSearchParams({ q }), signal),
    enabled: q.length >= 2,
    staleTime: 5 * 60_000,
  });
}

export function urlExportacao(caminho: string, params: URLSearchParams, extra?: Record<string, string>) {
  const p = new URLSearchParams(params);
  for (const [k, v] of Object.entries(extra ?? {})) p.set(k, v);
  return `${caminho}?${p}`;
}

export type { Filtros };
