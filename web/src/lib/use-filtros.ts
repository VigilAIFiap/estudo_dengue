"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { escreverFiltros, FILTROS_VAZIOS, lerFiltros, type Filtros } from "./filters";

/** Filtros globais sincronizados com a URL (compartilháveis e com histórico). */
export function useFiltros() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const filtros = useMemo(() => lerFiltros(new URLSearchParams(params.toString())), [params]);

  const definir = useCallback(
    (parcial: Partial<Filtros>) => {
      const proximo = escreverFiltros(new URLSearchParams(params.toString()), { ...filtros, ...parcial });
      proximo.delete("pagina");
      const qs = proximo.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [filtros, params, pathname, router],
  );

  const limpar = useCallback(() => definir(FILTROS_VAZIOS), [definir]);

  return { filtros, definir, limpar };
}

/** Parâmetro de página (fora dos filtros globais), também na URL. */
export function useParametro(chave: string): [string | null, (valor: string | null) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const valor = params.get(chave);
  const definir = useCallback(
    (novo: string | null) => {
      const p = new URLSearchParams(params.toString());
      if (novo == null || novo === "") p.delete(chave);
      else p.set(chave, novo);
      const qs = p.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [chave, params, pathname, router],
  );
  return [valor, definir];
}

/** Atualiza várias chaves de página numa única navegação. */
export function useDefinirParametros() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  return useCallback(
    (valores: Record<string, string | null>) => {
      const p = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(valores)) {
        if (v == null || v === "") p.delete(k);
        else p.set(k, v);
      }
      const qs = p.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );
}
