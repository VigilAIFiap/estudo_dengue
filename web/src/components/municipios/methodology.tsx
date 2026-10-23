import type { Schemas } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { NIVEL, type Nivel } from "@/lib/criticality";
import { CriticalityMeter } from "@/components/ui/criticality-badge";

/** Metodologia do score, exibida a partir dos parâmetros devolvidos pela API. */
export function Methodology({ m }: { m: Schemas["Metodologia"] }) {
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="grid gap-5 text-[13px] leading-6 text-ink-2 md:grid-cols-2">
      <div>
        <h3 className="mb-1 font-medium text-ink">Como o score é calculado</h3>
        <ol className="list-decimal space-y-1 pl-5">
          <li>Agrega por município notificador: notificações, óbitos (evolução 2 ou 3, regra do painel original) e hospitalizações.</li>
          <li>
            Mantém só municípios com mais notificações que o 1º quartil do recorte (hoje {fmtInt(m.q1)}). Os demais aparecem como “sem score”.
          </li>
          <li>
            Suaviza as taxas de óbito e hospitalização em direção à média do recorte, como se cada município tivesse{" "}
            {fmtInt(m.pseudo_casos_obito)} e {fmtInt(m.pseudo_casos_hospitalizacao)} notificações extras com a taxa média, respectivamente.
            Assim, 2 óbitos em 50 casos não viram uma letalidade extrema.
          </li>
          <li>
            Normaliza cada componente de 0 a 1 entre os municípios do recorte e soma: {pct(m.pesos.volume_log)} volume (log das notificações),{" "}
            {pct(m.pesos.taxa_obito)} taxa de óbito, {pct(m.pesos.taxa_hospitalizacao)} taxa de hospitalização. Multiplica por 100.
          </li>
          <li>
            Os componentes de óbito e hospitalização são multiplicados pela credibilidade n / (n + {fmtInt(m.casos_credibilidade)}): com{" "}
            {fmtInt(m.casos_credibilidade)} notificações valem metade; com 1.000, cerca de 91%.
          </li>
          <li>Municípios com menos de {fmtInt(m.minimo_casos_critico)} notificações não são classificados como Crítico (ficam no máximo em Alto).</li>
        </ol>
      </div>
      <div>
        <h3 className="mb-1 font-medium text-ink">Faixas e limites</h3>
        <ul className="mb-3 space-y-1">
          {m.cortes.map((c) => (
            <li key={c.nivel} className="flex items-center gap-2">
              <CriticalityMeter nivel={c.nivel} />
              <span className="w-14 text-ink">{c.nivel}</span>
              <span className="text-muted">{NIVEL[c.nivel as Nivel].descricao}</span>
            </li>
          ))}
        </ul>
        <p>
          O score é relativo: muda quando o período, a UF ou a classificação mudam, porque a normalização acontece dentro do recorte. É um
          indicador analítico do projeto para priorização, não uma classificação clínica nem um protocolo oficial de risco epidemiológico.
          Sem dados de população, não há taxa de incidência por habitante.
        </p>
      </div>
    </div>
  );
}
