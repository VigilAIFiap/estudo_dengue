import { z } from "zod";

const data = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

/** Filtros globais como aparecem na URL. Ausência = padrão definido pela API. */
export const filtrosSchema = z.object({
  inicio: data.optional().catch(undefined),
  fim: data.optional().catch(undefined),
  uf: z.array(z.string().regex(/^[A-Z]{2}$/)).catch([]),
  municipio: z.coerce.number().int().positive().optional().catch(undefined),
  classificacao: z.array(z.coerce.number().int()).catch([]),
});

export type Filtros = z.infer<typeof filtrosSchema>;

export const FILTROS_VAZIOS: Filtros = { uf: [], classificacao: [] };

export function lerFiltros(params: URLSearchParams): Filtros {
  return filtrosSchema.parse({
    inicio: params.get("inicio") ?? undefined,
    fim: params.get("fim") ?? undefined,
    uf: params.getAll("uf"),
    municipio: params.get("municipio") ?? undefined,
    classificacao: params.getAll("classificacao"),
  });
}

/** Parâmetros para a API: aplica o período padrão quando não há escolha explícita. */
export function paraParametros(f: Filtros, padrao?: { inicio: string; fim: string }): URLSearchParams {
  const p = new URLSearchParams();
  const inicio = f.inicio ?? padrao?.inicio;
  const fim = f.fim ?? padrao?.fim;
  if (inicio) p.set("inicio", inicio);
  if (fim) p.set("fim", fim);
  for (const uf of [...f.uf].sort()) p.append("uf", uf);
  if (f.municipio) p.set("municipio", String(f.municipio));
  for (const c of [...f.classificacao].sort((a, b) => a - b)) p.append("classificacao", String(c));
  return p;
}

/** Mescla os filtros nos parâmetros atuais da URL, preservando chaves de página. */
export function escreverFiltros(atuais: URLSearchParams, f: Filtros): URLSearchParams {
  const p = new URLSearchParams(atuais);
  for (const chave of ["inicio", "fim", "uf", "municipio", "classificacao"]) p.delete(chave);
  for (const [k, v] of paraParametros(f)) p.append(k, v);
  return p;
}

export function contarAtivos(f: Filtros): number {
  return (f.inicio || f.fim ? 1 : 0) + (f.uf.length ? 1 : 0) + (f.municipio ? 1 : 0) + (f.classificacao.length ? 1 : 0);
}
