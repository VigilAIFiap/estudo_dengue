import type { Schemas } from "./api";
import { useMeta } from "./queries";

export type BaseMunicipal = Schemas["Meta"]["base_municipal"];

/** Rótulo do município usado na análise: residência do paciente ou município que notificou. */
export function rotuloBase(base: BaseMunicipal | undefined): string {
  return base === "residencia" ? "município de residência" : "município notificador";
}

export function useRotuloBase(): string {
  return rotuloBase(useMeta().data?.base_municipal);
}

export function inicialMaiuscula(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
