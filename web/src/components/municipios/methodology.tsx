import type { Schemas } from "@/lib/api";
import { fmtDec, fmtInt, fmtPct } from "@/lib/format";
import { NIVEL, type Nivel } from "@/lib/criticality";
import { CriticalityMeter } from "@/components/ui/criticality-badge";
import { Formula } from "@/components/ui/formula";
import { useRotuloBase } from "@/lib/base-municipal";

const virgula = (n: number, casas = 2) => n.toFixed(casas).replace(".", ",");

/** Exemplo ilustrativo (números fictícios) que percorre a fórmula do início ao fim. */
function calcularExemplo(m: Schemas["Metodologia"]) {
  const casos = 4500;
  const minimo = 9;
  const maximo = 80000;
  const percentilObito = 0.9;
  const percentilHosp = 0.8;
  const v = (Math.log1p(casos) - Math.log1p(minimo)) / (Math.log1p(maximo) - Math.log1p(minimo));
  const s = m.pesos.taxa_obito * percentilObito + m.pesos.taxa_hospitalizacao * percentilHosp;
  const score = 100 * v * s;
  const nivel = m.cortes.find((c) => c.minimo == null || score >= c.minimo)?.nivel;
  return { casos, minimo, maximo, percentilObito, percentilHosp, v, s, score, nivel };
}

/** Metodologia do score, exibida a partir dos parâmetros devolvidos pela API. */
export function Methodology({ m }: { m: Schemas["Metodologia"] }) {
  const rotuloBase = useRotuloBase();
  const wo = virgula(m.pesos.taxa_obito, 1);
  const wh = virgula(m.pesos.taxa_hospitalizacao, 1);
  const k = m.suavizacao_casos;
  const ex = calcularExemplo(m);
  const taxaGeral = 0.0012;
  const taxaBruta = 4 / 62;
  const taxaSuavizada = (4 + k * taxaGeral) / (62 + k);

  return (
    <div className="grid gap-6 text-[13px] leading-6 text-ink-2 lg:grid-cols-2">
      <div className="space-y-3">
        <p>
          O score resume, de 0 a 100, quanto cada município pesa no recorte escolhido. Ele combina duas ideias: <strong className="text-ink">quantos casos</strong>{" "}
          o município tem (volume) e <strong className="text-ink">quão graves</strong> eles são (severidade). Como as duas partes se{" "}
          <strong className="text-ink">multiplicam</strong>, um município só chega a um nível alto quando tem muitos casos e casos graves ao mesmo tempo.
        </p>

        <div>
          <h3 className="font-medium text-ink">Fórmula</h3>
          <Formula legenda="Fórmula do score de criticidade, calculada entre os municípios do recorte.">
            {`score = 100 × V × S

V = ( ln(1 + casos) − ln(1 + casos_mín) ) / ( ln(1 + casos_máx) − ln(1 + casos_mín) )

S = ${wo} × P(óbito*) + ${wh} × P(hosp*)

x* = ( eventos + k × taxa_geral ) / ( casos + k )        com k = ${k}`}
          </Formula>
        </div>

        <div>
          <h3 className="font-medium text-ink">O que cada termo significa</h3>
          <dl className="mt-1 space-y-1.5">
            <div>
              <dt className="inline font-medium text-ink">casos</dt>
              <dd className="inline">
                {" "}
                — notificações do município no recorte, agregadas por {rotuloBase}. <em>casos_mín</em> e <em>casos_máx</em> são o menor e o maior valor
                entre os municípios com score.
              </dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">V (fator de volume)</dt>
              <dd className="inline">
                {" "}
                — vai de 0 a 1. Usa o logaritmo para que as maiores cidades não esmaguem todas as outras. É o multiplicador: quem tem poucos casos tem V
                baixo, e o score fica baixo mesmo com taxas altas.
              </dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">S (severidade)</dt>
              <dd className="inline">
                {" "}
                — vai de 0 a 1. Combina a posição do município na taxa de óbito ({Math.round(m.pesos.taxa_obito * 100)}%) e na taxa de hospitalização (
                {Math.round(m.pesos.taxa_hospitalizacao * 100)}%).
              </dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">P( · )</dt>
              <dd className="inline">
                {" "}
                — posição percentual do município entre os do recorte, em ordem crescente da taxa. 0,5 significa estar no meio; perto de 1, entre os piores.
                Usar a posição, e não o valor da taxa, impede que um único município atípico distorça a escala dos demais.
              </dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">x* (taxa suavizada)</dt>
              <dd className="inline">
                {" "}
                — taxa de óbito (evolução 2) ou de hospitalização (HOSPITALIZ = 1), puxada em direção à <em>taxa_geral</em> do recorte com o peso de{" "}
                <em>k</em> = {k} casos. Com poucos casos, a taxa do município quase não sai da média; com muitos, vale a taxa observada.
              </dd>
            </div>
          </dl>
        </div>

        <p>
          <strong className="text-ink">Quem entra:</strong> só municípios com mais notificações que o 1º quartil do recorte (hoje {fmtInt(m.q1)}). Os demais
          aparecem como “sem score”, porque não há dados suficientes para avaliá-los.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="font-medium text-ink">Exemplo ilustrativo (números fictícios)</h3>
          <ol className="mt-1 list-decimal space-y-1 pl-5">
            <li>
              Em um recorte cujos municípios vão de {fmtInt(ex.minimo)} a {fmtInt(ex.maximo)} notificações, um município com {fmtInt(ex.casos)} notificações
              tem <strong className="text-ink">V = {virgula(ex.v)}</strong>.
            </li>
            <li>
              Se ele está na posição {virgula(ex.percentilObito)} em óbito e {virgula(ex.percentilHosp)} em hospitalização, a severidade é{" "}
              {wo} × {virgula(ex.percentilObito)} + {wh} × {virgula(ex.percentilHosp)} = <strong className="text-ink">S = {virgula(ex.s)}</strong>.
            </li>
            <li>
              O score é 100 × {virgula(ex.v)} × {virgula(ex.s)} ≈ <strong className="text-ink">{fmtDec(ex.score)}</strong>
              {ex.nivel && <>, nível {ex.nivel}</>}.
            </li>
            <li>
              Suavização: um município com 62 notificações e 4 óbitos tem taxa bruta de {fmtPct(taxaBruta)}. Com taxa geral de {fmtPct(taxaGeral, 2)} e k ={" "}
              {k}, a taxa suavizada fica em {fmtPct(taxaSuavizada)}: ainda acima da média, mas sem o exagero de poucos casos.
            </li>
          </ol>
        </div>

        <div>
          <h3 className="mb-1 font-medium text-ink">Faixas do score</h3>
          <ul className="space-y-1">
            {m.cortes.map((c) => (
              <li key={c.nivel} className="flex items-center gap-2">
                <CriticalityMeter nivel={c.nivel} />
                <span className="w-14 text-ink">{c.nivel}</span>
                <span className="text-muted">{NIVEL[c.nivel as Nivel].descricao}</span>
              </li>
            ))}
          </ul>
        </div>

        <p>
          <strong className="text-ink">Limites:</strong> o score é relativo, porque o volume e as posições são calculados dentro do recorte: muda quando o
          período, a UF ou a classificação mudam. Sem dados de população, não há taxa de incidência por habitante. É um indicador analítico do projeto para
          priorização, não uma classificação clínica nem um protocolo oficial de risco epidemiológico.
        </p>
      </div>
    </div>
  );
}
