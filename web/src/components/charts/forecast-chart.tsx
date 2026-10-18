"use client";

import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Schemas } from "@/lib/api";
import { fmtCompacto, fmtInt, fmtMes } from "@/lib/format";
import { ChartTooltipBox, Legenda } from "./chart-tooltip";
import { EIXO, SERIE } from "./theme";

type Previsao = Schemas["Previsao"];
type Linha = { mes: string; observado?: number; previsto?: number; faixa?: [number, number] };

/** Observado (linha contínua) e projeção (tracejada, com intervalo de 95%). */
export function ForecastChart({ dados, altura = 320 }: { dados: Previsao; altura?: number }) {
  const linhas: Linha[] = [
    ...dados.historico.map((h) => ({ mes: h.mes, observado: h.casos })),
    ...dados.previsao.map((p) => ({ mes: p.mes, previsto: p.previsao, faixa: [p.inferior, p.superior] as [number, number] })),
  ];
  const projeta = dados.previsao.length > 0;
  return (
    <figure className="flex flex-col gap-3">
      <div style={{ height: altura }} role="img" aria-label="Casos mensais observados e projeção do modelo">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={linhas} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={SERIE.grade} />
            <XAxis dataKey="mes" {...EIXO} tickFormatter={fmtMes} minTickGap={20} />
            <YAxis {...EIXO} width={56} tickFormatter={(v: number) => fmtCompacto(v)} />
            <Tooltip
              content={({ active, payload }) => {
                const d = payload?.[0]?.payload as Linha | undefined;
                if (!active || !d) return null;
                return (
                  <ChartTooltipBox
                    titulo={fmtMes(d.mes)}
                    linhas={
                      d.observado != null
                        ? [{ cor: SERIE.principal, rotulo: "Observado", valor: fmtInt(d.observado) }]
                        : [
                            { cor: SERIE.complementar, tracejado: true, rotulo: "Projeção", valor: fmtInt(d.previsto ?? 0) },
                            { rotulo: "Intervalo 95%", valor: `${fmtInt(d.faixa?.[0] ?? 0)} a ${fmtInt(d.faixa?.[1] ?? 0)}` },
                          ]
                    }
                  />
                );
              }}
            />
            {projeta && <Area dataKey="faixa" stroke="none" fill={SERIE.complementar} fillOpacity={0.12} isAnimationActive={false} />}
            <Line dataKey="observado" stroke={SERIE.principal} strokeWidth={2} dot={{ r: 2.5, fill: SERIE.principal }} isAnimationActive={false} connectNulls={false} />
            {projeta && (
              <Line dataKey="previsto" stroke={SERIE.complementar} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption>
        <Legenda
          itens={[
            { cor: SERIE.principal, rotulo: "Casos confirmados por mês (definição do modelo)", tipo: "linha" },
            ...(projeta
              ? [
                  { cor: SERIE.complementar, rotulo: "Projeção SARIMA", tipo: "tracejado" as const },
                  { cor: "rgb(15 157 154 / 0.25)", rotulo: "Intervalo de previsão 95%" },
                ]
              : []),
          ]}
        />
      </figcaption>
    </figure>
  );
}
