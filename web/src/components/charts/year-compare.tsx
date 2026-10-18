"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Schemas } from "@/lib/api";
import { fmtCompacto, fmtInt } from "@/lib/format";
import { ChartTooltipBox, Legenda } from "./chart-tooltip";
import { EIXO, SERIE } from "./theme";

type Anual = Schemas["ComparacaoAnual"];

/** Um traço por ano epidemiológico, alinhado pela semana (SE 1–53). */
export function YearCompare({ dados, metrica, altura = 300 }: { dados: Anual; metrica: "notificacoes" | "confirmados"; altura?: number }) {
  const anos = [...dados.anos].sort((a, b) => a.ano - b.ano);
  const recente = anos.at(-1)?.ano;
  const linhas = Array.from({ length: 53 }, (_, i) => {
    const semana = i + 1;
    const linha: Record<string, number | undefined> & { semana: number } = { semana };
    for (const a of anos) {
      // A última semana parcial não entra na linha: pareceria uma queda que não aconteceu.
      const parcial = a.ultima_semana_parcial && semana === a.ultima_semana;
      linha[String(a.ano)] = parcial ? undefined : a.semanas.find((s) => s.semana === semana)?.[metrica];
    }
    return linha;
  });
  const cor = (ano: number) => (ano === recente ? SERIE.principal : SERIE.anterior);

  return (
    <figure className="flex flex-col gap-3">
      <div style={{ height: altura }} role="img" aria-label={`Comparação entre anos por semana epidemiológica: ${anos.map((a) => a.ano).join(" e ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={linhas} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={SERIE.grade} />
            <XAxis dataKey="semana" {...EIXO} ticks={[1, 10, 20, 30, 40, 53]} tickFormatter={(s: number) => `SE ${s}`} />
            <YAxis {...EIXO} width={56} tickFormatter={(v: number) => fmtCompacto(v)} />
            <Tooltip
              cursor={{ stroke: SERIE.anterior, strokeDasharray: "3 3" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <ChartTooltipBox
                    titulo={`Semana epidemiológica ${label}`}
                    linhas={anos.map((a) => {
                      const v = payload[0]?.payload?.[String(a.ano)] as number | undefined;
                      return { cor: cor(a.ano), rotulo: String(a.ano), valor: v == null ? "sem dados" : fmtInt(v) };
                    })}
                  />
                );
              }}
            />
            {anos.map((a) => (
              <Line
                key={a.ano}
                dataKey={String(a.ano)}
                stroke={cor(a.ano)}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption>
        <Legenda
          itens={anos.map((a) => ({
            cor: cor(a.ano),
            tipo: "linha" as const,
            rotulo: a.ultima_semana_parcial
              ? `${a.ano} (até a SE ${a.ultima_semana - 1}; SE ${a.ultima_semana} incompleta, omitida)`
              : String(a.ano),
          }))}
        />
      </figcaption>
    </figure>
  );
}
