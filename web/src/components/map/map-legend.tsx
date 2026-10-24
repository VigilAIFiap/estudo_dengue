import type { BaseMunicipal } from "@/lib/base-municipal";
import { NIVEL, NIVEIS, SEM_SCORE } from "@/lib/criticality";
import { fmtInt } from "@/lib/format";
import { CriticalityMeter } from "@/components/ui/criticality-badge";
import { RAMPA, ROTULO_CAMADA, SEM_NOTIFICACAO, type Camada } from "./brazil-map";

export type ContagensMapa = {
  semNotificacao: number;
  semScore: number;
  q1: number;
  base: BaseMunicipal;
  semResidencia: number;
};

const NOTA_EM_BRANCO =
  "Em branco: sugere um estado silencioso, no qual as notificações permanecem em atraso até o período exportado.";

function notaMunicipio(c: ContagensMapa): string {
  if (c.base === "residencia") {
    return c.semResidencia > 0
      ? `Os dados usam o município de residência do paciente. ${fmtInt(c.semResidencia)} notificações sem residência válida ficaram no município de notificação.`
      : "Os dados usam o município de residência do paciente.";
  }
  return "Os dados usam o município de notificação (onde fica a unidade de saúde), não o de residência. Cidades sem unidade podem ter casos registrados no município vizinho.";
}

export function MapLegend({ camada, cortes, contagens }: { camada: Camada; cortes: number[]; contagens?: ContagensMapa }) {
  if (camada === "score") {
    return (
      <div className="flex flex-col gap-2">
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-2" aria-label="Legenda: nível de criticidade">
          {NIVEIS.map((n) => (
            <li key={n} className="flex items-center gap-1.5">
              <span aria-hidden className="size-3 rounded-[3px]" style={{ background: NIVEL[n].fill }} />
              <CriticalityMeter nivel={n} />
              {n} <span className="text-muted">({NIVEL[n].descricao.toLowerCase()})</span>
            </li>
          ))}
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="size-3 rounded-[3px]" style={{ background: SEM_SCORE.fill }} />
            Sem score
            {contagens && (
              <span className="text-muted">
                ({fmtInt(contagens.semScore)} municípios com até {fmtInt(contagens.q1)} notificações)
              </span>
            )}
          </li>
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="size-3 rounded-[3px] border border-line" style={{ background: SEM_NOTIFICACAO }} />
            Sem notificação
            {contagens && <span className="text-muted">({fmtInt(contagens.semNotificacao)} municípios)</span>}
          </li>
        </ul>
        <p className="text-2xs text-muted">
          {NOTA_EM_BRANCO}
          {contagens && <> {notaMunicipio(contagens)}</>}
        </p>
      </div>
    );
  }
  const limites = [0, ...cortes];
  return (
    <div className="flex flex-col gap-1.5" aria-label={`Legenda: ${ROTULO_CAMADA[camada]}`}>
      <div className="flex items-stretch gap-[2px]">
        <span className="h-2.5 w-8 rounded-l-[3px] border border-line" style={{ background: SEM_NOTIFICACAO }} title="Zero" />
        {RAMPA.slice(0, limites.length).map((c, i) => (
          <span key={c} className="h-2.5 flex-1 last:rounded-r-[3px]" style={{ background: c, minWidth: 28 }} title={faixa(limites, i)} />
        ))}
      </div>
      <div className="flex gap-[2px] text-2xs text-muted">
        <span className="w-8">0</span>
        {limites.map((_, i) => (
          <span key={i} className="num flex-1 truncate" style={{ minWidth: 28 }}>
            {faixa(limites, i)}
          </span>
        ))}
      </div>
      <p className="text-2xs text-muted">
        Classes por quantis entre os municípios com ao menos um registro. {NOTA_EM_BRANCO}
        {contagens && <> Sem notificação no período: {fmtInt(contagens.semNotificacao)} municípios. {notaMunicipio(contagens)}</>}
      </p>
    </div>
  );
}

function faixa(limites: number[], i: number) {
  const de = Math.floor(limites[i]!) + 1;
  const ate = limites[i + 1];
  return ate == null ? `${fmtInt(de)}+` : de >= Math.floor(ate) ? fmtInt(Math.floor(ate)) : `${fmtInt(de)}–${fmtInt(Math.floor(ate))}`;
}
