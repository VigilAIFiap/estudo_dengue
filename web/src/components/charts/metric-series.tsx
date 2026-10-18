"use client";

import { Bar, BarChart, Brush, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Schemas } from "@/lib/api";
import { fmtCompacto, fmtData, fmtInt } from "@/lib/format";
import { ChartTooltipBox } from "./chart-tooltip";
import { EIXO, SERIE } from "./theme";

type Ponto = Schemas["PontoSerie"];
export type MetricaSerie = "notificacoes" | "confirmados" | "graves" | "hospitalizacoes" | "obitos";

export const ROTULO_METRICA: Record<MetricaSerie, string> = {
  notificacoes: "Notificações",
  confirmados: "Confirmados",
  graves: "Sinais de alarme e graves",
  hospitalizacoes: "Hospitalizações",
  obitos: "Óbitos pelo agravo",
};

/** Série de uma métrica, com seleção de intervalo (brush) e períodos parciais hachurados. */
export function MetricSeries({ serie, metrica, altura = 320 }: { serie: Ponto[]; metrica: MetricaSerie; altura?: number }) {
  const cor = metrica === "confirmados" || metrica === "notificacoes" ? SERIE.principal : SERIE.complementar;
  return (
    <div style={{ height: altura }} role="img" aria-label={`${ROTULO_METRICA[metrica]} por período, ${serie.length} períodos`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={serie} margin={{ top: 8, right: 4, left: -4, bottom: 0 }} barCategoryGap={2}>
          <defs>
            <pattern id={`hachura-${metrica}`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill={cor} opacity={0.45} />
              <line x1="0" y1="0" x2="0" y2="5" stroke="#fff" strokeWidth="2" />
            </pattern>
          </defs>
          <CartesianGrid vertical={false} stroke={SERIE.grade} />
          <XAxis dataKey="periodo" {...EIXO} minTickGap={28} tickFormatter={(p: string) => p.replace("/20", "/")} />
          <YAxis {...EIXO} width={56} tickFormatter={(v: number) => fmtCompacto(v)} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: "rgb(37 99 235 / 0.06)" }}
            content={({ active, payload }) => {
              const d = payload?.[0]?.payload as Ponto | undefined;
              if (!active || !d) return null;
              return (
                <ChartTooltipBox
                  titulo={`${d.periodo}, ${fmtData(d.inicio)} a ${fmtData(d.fim)}`}
                  linhas={[
                    { cor, rotulo: ROTULO_METRICA[metrica], valor: fmtInt(d[metrica]) },
                    ...(metrica !== "notificacoes" ? [{ rotulo: "Notificações", valor: fmtInt(d.notificacoes) }] : []),
                  ]}
                  nota={d.parcial ? "Período parcial: o recorte ou os dados não cobrem o período inteiro." : undefined}
                />
              );
            }}
          />
          <Bar
            dataKey={metrica}
            isAnimationActive={false}
            radius={[3, 3, 0, 0]}
            shape={(props: unknown) => {
              const p = props as { x: number; y: number; width: number; height: number; payload: Ponto };
              if (!p.height || p.height <= 0) return <g />;
              const r = Math.min(3, p.width / 2);
              const { x, y, width: w, height: h } = p;
              return (
                <path
                  d={`M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`}
                  fill={p.payload.parcial ? `url(#hachura-${metrica})` : cor}
                />
              );
            }}
          />
          {serie.length > 20 && (
            <Brush dataKey="periodo" height={22} stroke={SERIE.anterior} travellerWidth={8} tickFormatter={() => ""} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
