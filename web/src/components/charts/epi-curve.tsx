"use client";

import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Schemas } from "@/lib/api";
import { fmtCompacto, fmtData, fmtInt } from "@/lib/format";
import { ChartTooltipBox, Legenda } from "./chart-tooltip";
import { EIXO, SERIE } from "./theme";

type Ponto = Schemas["PontoSerie"];

type Linha = {
  periodo: string;
  inicio: string;
  fim: string;
  parcial: boolean;
  confirmados: number;
  outras: number;
  notificacoes: number;
  anterior?: number;
  anteriorPeriodo?: string;
};

/**
 * Curva epidêmica por semana epidemiológica: barras empilhadas (confirmados +
 * demais notificações) e, quando houver cobertura, a mesma semana 52 semanas antes.
 */
export function EpiCurve({ serie, anterior, altura = 300 }: { serie: Ponto[]; anterior?: Ponto[]; altura?: number }) {
  const dados: Linha[] = serie.map((p, i) => ({
    periodo: p.periodo,
    inicio: p.inicio,
    fim: p.fim,
    parcial: p.parcial,
    confirmados: p.confirmados,
    outras: p.notificacoes - p.confirmados,
    notificacoes: p.notificacoes,
    // Em semana parcial a comparação também seria parcial e pareceria uma queda.
    anterior: p.parcial ? undefined : anterior?.[i]?.notificacoes,
    anteriorPeriodo: anterior?.[i]?.periodo,
  }));
  const temAnterior = !!anterior?.length;
  const parciais = dados.some((d) => d.parcial);

  return (
    <figure className="flex flex-col gap-3">
      <div style={{ height: altura }} role="img" aria-label={`Curva epidêmica semanal com ${dados.length} semanas`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={dados} margin={{ top: 8, right: 4, left: -4, bottom: 0 }} barCategoryGap={2}>
            <defs>
              <pattern id="hachura-conf" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="5" height="5" fill={SERIE.principal} opacity={0.45} />
                <line x1="0" y1="0" x2="0" y2="5" stroke="#fff" strokeWidth="2" />
              </pattern>
              <pattern id="hachura-outras" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="5" height="5" fill={SERIE.principalClaro} opacity={0.6} />
                <line x1="0" y1="0" x2="0" y2="5" stroke="#fff" strokeWidth="2" />
              </pattern>
            </defs>
            <CartesianGrid vertical={false} stroke={SERIE.grade} />
            <XAxis dataKey="periodo" {...EIXO} interval="preserveStartEnd" minTickGap={24} tickFormatter={(p: string) => p.replace("/20", "/")} />
            <YAxis {...EIXO} tickFormatter={(v: number) => fmtCompacto(v)} width={56} />
            <Tooltip
              cursor={{ fill: "rgb(37 99 235 / 0.06)" }}
              content={({ active, payload }) => {
                const d = payload?.[0]?.payload as Linha | undefined;
                if (!active || !d) return null;
                return (
                  <ChartTooltipBox
                    titulo={`${d.periodo}, ${fmtData(d.inicio)} a ${fmtData(d.fim)}`}
                    linhas={[
                      { cor: SERIE.principal, rotulo: "Confirmados", valor: fmtInt(d.confirmados) },
                      { cor: SERIE.principalClaro, rotulo: "Demais notificações", valor: fmtInt(d.outras) },
                      { rotulo: "Total de notificações", valor: fmtInt(d.notificacoes) },
                      ...(d.anterior != null
                        ? [{ cor: SERIE.anterior, tracejado: true, rotulo: `Mesma semana (${d.anteriorPeriodo})`, valor: fmtInt(d.anterior) }]
                        : []),
                    ]}
                    nota={d.parcial ? "Semana parcial: o período ou os dados não cobrem os 7 dias." : undefined}
                  />
                );
              }}
            />
            <Bar
              dataKey="confirmados"
              stackId="s"
              isAnimationActive={false}
              shape={(props: unknown) => <Coluna {...(props as ColunaProps)} campo="conf" />}
            />
            <Bar
              dataKey="outras"
              stackId="s"
              isAnimationActive={false}
              shape={(props: unknown) => <Coluna {...(props as ColunaProps)} campo="outras" topo />}
            />
            {temAnterior && (
              <Line
                dataKey="anterior"
                type="monotone"
                stroke={SERIE.anterior}
                strokeWidth={2}
                strokeDasharray="4 3"
                dot={false}
                activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <Legenda
          itens={[
            { cor: SERIE.principal, rotulo: "Confirmados (dengue, sinais de alarme, grave)" },
            { cor: SERIE.principalClaro, rotulo: "Demais notificações" },
            ...(temAnterior ? [{ cor: SERIE.anterior, rotulo: "Notificações, mesmas semanas do ano anterior", tipo: "tracejado" as const }] : []),
            ...(parciais ? [{ cor: "", rotulo: "Semana parcial", tipo: "hachura" as const }] : []),
          ]}
        />
      </figcaption>
    </figure>
  );
}

type ColunaProps = { x: number; y: number; width: number; height: number; payload: Linha };

function Coluna({ x, y, width, height, payload, campo, topo }: ColunaProps & { campo: "conf" | "outras"; topo?: boolean }) {
  if (!height || height <= 0) return null;
  const fill = payload.parcial
    ? `url(#hachura-${campo})`
    : campo === "conf"
      ? SERIE.principal
      : SERIE.principalClaro;
  const r = topo ? Math.min(3, width / 2) : 0;
  // Topo arredondado só no último segmento; 1px de folga entre segmentos.
  const h = topo ? height : Math.max(height - 1, 0);
  const caminho = topo
    ? `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${y + h} Z`
    : `M${x},${y} H${x + width} V${y + h} H${x} Z`;
  return <path d={caminho} fill={fill} />;
}
