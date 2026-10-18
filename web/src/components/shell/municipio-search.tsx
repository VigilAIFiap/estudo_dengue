"use client";

import { useRouter } from "next/navigation";
import { MunicipioCombobox } from "@/components/ui/municipio-combobox";
import { useHrefComFiltros } from "./app-sidebar";

/** Busca global: abre o detalhe do município mantendo os filtros. */
export function MunicipioSearch() {
  const router = useRouter();
  const href = useHrefComFiltros();
  return (
    <MunicipioCombobox
      className="max-w-sm"
      placeholder="Buscar município"
      onSelecionar={(m) => {
        const destino = href("/municipios");
        router.push(`${destino}${destino.includes("?") ? "&" : "?"}m=${m.id_municip}`);
      }}
    />
  );
}
