import { Formula } from "@/components/ui/formula";
import { fmtData } from "@/lib/format";

const PARAMETROS: [string, string][] = [
  ["Modelo", "SARIMA com sazonalidade anual (m = 12), ordem escolhida por auto_arima (pmdarima)."],
  [
    "Tamanho mínimo da série",
    "24 meses completos para ajustar o modelo (duas estações). A validação por janelas exige 33 (24 de treino e 9 de teste); sem ela, nenhuma previsão é exibida.",
  ],
  ["Horizonte", "12 meses, com intervalo de previsão de 95%."],
  ["Validação", "Janelas móveis: 3 dobras de 3 meses, comparadas ao baseline sazonal ingênuo (repete o mesmo mês do ano anterior)."],
  ["Definição de caso", "Somente classificação final 10, 11 e 12: dengue, dengue com sinais de alarme e dengue grave."],
];

/** Explica, em linguagem direta, como a previsão é construída e como lê-la. */
export function MetodologiaPrevisao({ dataReferencia }: { dataReferencia: string }) {
  return (
    <div className="grid gap-6 text-[13px] leading-6 text-ink-2 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-4">
        <p>
          A previsão olha para o <strong className="text-ink">histórico mensal de casos confirmados</strong>, aprende o padrão de subida e queda que se repete a
          cada ano e o projeta para os próximos 12 meses. Ela não usa nenhuma outra informação além da própria série.
        </p>

        <ol className="list-decimal space-y-2.5 pl-5">
          <li>
            <strong className="text-ink">Série de entrada.</strong> Casos confirmados (classificação final 10, 11 ou 12) somados por mês de notificação, no
            recorte geográfico escolhido, até {fmtData(dataReferencia)}. O mês em curso é descartado por estar incompleto. O filtro de período não se aplica.
          </li>
          <li>
            <strong className="text-ink">Modelo.</strong> SARIMA(p, d, q)(P, D, Q)₁₂, que descreve cada mês a partir dos meses anteriores e dos mesmos meses
            dos anos anteriores:
            <Formula legenda="B é o operador de defasagem (B·y_t = y_t−1); y_t são os casos do mês t; ε_t é o erro aleatório.">
              {`φ(B) · Φ(B^12) · (1 − B)^d · (1 − B^12)^D · y_t  =  θ(B) · Θ(B^12) · ε_t`}
            </Formula>
            φ e θ são as partes autorregressiva e de média móvel; Φ e Θ são as mesmas na escala sazonal de 12 meses; d e D são as diferenciações simples e
            sazonal que tornam a série estável.
          </li>
          <li>
            <strong className="text-ink">Escolha da ordem.</strong> O auto_arima testa combinações (p e q até 3; P e Q até 2), define d e D por testes
            estatísticos e fica com a de menor AIC, um critério que equilibra ajuste e simplicidade.
          </li>
          <li>
            <strong className="text-ink">Projeção.</strong> 12 meses à frente, com intervalo de previsão de 95%. Valores negativos são truncados em zero e a
            previsão pontual é arredondada para número inteiro.
          </li>
          <li>
            <strong className="text-ink">Validação.</strong> O modelo é reajustado 3 vezes e prevê 3 meses de cada vez nos últimos 9 meses, sem enxergar
            esses meses. O erro é comparado ao de um baseline simples que repete o mesmo mês do ano anterior:
            <Formula legenda="n = 9 meses de teste; y é o valor observado e ŷ o previsto. “Supera o baseline” significa MAE do modelo menor que o do baseline.">
              {`MAE = (1 / n) × Σ | y_t − ŷ_t |          baseline: ŷ_t = y_t−12`}
            </Formula>
          </li>
        </ol>

        <div>
          <h3 className="font-medium text-ink">Como ler o resultado</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>“Próximo mês” é a previsão pontual do primeiro mês projetado; a faixa sombreada do gráfico é o intervalo de 95%.</li>
            <li>O MAE é o erro médio, em casos por mês, nos meses de teste. Quanto menor, melhor, mas são apenas 9 meses: não garante o acerto futuro.</li>
            <li>Se o modelo não superar o baseline, a previsão não traz ganho sobre simplesmente repetir o ano anterior.</li>
          </ul>
        </div>
      </div>

      <dl className="flex flex-col gap-3 self-start rounded-control border border-line bg-canvas p-4">
        {PARAMETROS.map(([k, v]) => (
          <div key={k}>
            <dt className="font-medium text-ink">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
        <div>
          <dt className="font-medium text-ink">Data de referência</dt>
          <dd>{fmtData(dataReferencia)}, última notificação carregada.</dd>
        </div>
      </dl>
    </div>
  );
}
