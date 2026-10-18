"use client";

import { useQuery } from "@tanstack/react-query";
import { geoArea, geoMercator, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { select } from "d3-selection";
import "d3-transition";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { Maximize2, Minus, Plus } from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import type { Schemas } from "@/lib/api";
import { estiloNivel, SEM_SCORE } from "@/lib/criticality";
import { fmtDec, fmtInt } from "@/lib/format";
import { CriticalityBadge } from "@/components/ui/criticality-badge";

type Ponto = Schemas["PontoMapa"];
export type Camada = "notificacoes" | "confirmados" | "obitos" | "hospitalizacoes" | "score";

export const ROTULO_CAMADA: Record<Camada, string> = {
  notificacoes: "Notificações",
  confirmados: "Casos confirmados",
  obitos: "Óbitos pelo agravo",
  hospitalizacoes: "Hospitalizações",
  score: "Score de criticidade",
};

/** Escala sequencial de um só matiz (azul), do claro ao escuro. */
const RAMPA = ["#dbe6fd", "#b4cbfa", "#83a9f5", "#4f82ec", "#2563eb", "#1a47b8", "#132f7a"];
const SEM_NOTIFICACAO = "#f1f4f8";

type Props = {
  pontos: Ponto[];
  camada: Camada;
  selecionado: number | null;
  onSelecionar: (id: number | null) => void;
  ufFoco: string[];
  altura: number;
};

type Props_ = { properties: { cod: string; uf: string } };

function useMalha() {
  return useQuery({
    queryKey: ["malha-municipal"],
    queryFn: async ({ signal }) => {
      const r = await fetch("/geo/municipios.topo.json", { signal });
      if (!r.ok) throw new Error("Não foi possível carregar a malha municipal (public/geo/municipios.topo.json).");
      return (await r.json()) as Topology<{ mun: GeometryCollection<{ cod: string; uf: string }> }>;
    },
    staleTime: Infinity,
  });
}

/** Quebras por quantis entre os municípios com valor > 0 (distribuição muito assimétrica). */
export function quebras(valores: number[], classes = RAMPA.length): number[] {
  const positivos = valores.filter((v) => v > 0).sort((a, b) => a - b);
  if (!positivos.length) return [];
  const q = new Set<number>();
  for (let i = 1; i < classes; i++) q.add(positivos[Math.floor((i / classes) * (positivos.length - 1))]!);
  return [...q];
}

function corPorValor(v: number, cortes: number[]) {
  if (v <= 0) return SEM_NOTIFICACAO;
  let i = 0;
  while (i < cortes.length && v > cortes[i]!) i++;
  return RAMPA[Math.min(i, RAMPA.length - 1)]!;
}

export function useEscala(pontos: Ponto[], camada: Camada) {
  return useMemo(() => {
    const cortes = camada === "score" ? [] : quebras(pontos.map((p) => p[camada]));
    const cor = (p: Ponto | undefined) => {
      if (!p) return SEM_NOTIFICACAO;
      if (camada === "score") return estiloNivel(p.nivel)?.fill ?? SEM_SCORE.fill;
      return corPorValor(p[camada], cortes);
    };
    return { cortes, cor };
  }, [pontos, camada]);
}

export function BrazilMap({ pontos, camada, selecionado, onSelecionar, ufFoco, altura }: Props) {
  const malha = useMalha();
  const contêiner = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const grupo = useRef<SVGGElement>(null);
  const comportamento = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [largura, setLargura] = useState(800);
  const [escalaZoom, setEscalaZoom] = useState(1);
  const [hover, setHover] = useState<{ id: number; x: number; y: number } | null>(null);

  useEffect(() => {
    const el = contêiner.current;
    if (!el) return;
    const obs = new ResizeObserver(([e]) => e && setLargura(Math.max(280, Math.round(e.contentRect.width))));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const porId = useMemo(() => new Map(pontos.map((p) => [p.id, p])), [pontos]);
  const { cor } = useEscala(pontos, camada);

  const geo = useMemo(() => {
    if (!malha.data) return null;
    const topo = malha.data;
    const municipios = (feature(topo, topo.objects.mun).features as unknown as (GeoPermissibleObjects & Props_)[]).map(reorientar);
    const uf = (g: unknown) => (g as Props_).properties.uf;
    const fronteirasUf = mesh(topo, topo.objects.mun, (a, b) => a !== b && uf(a) !== uf(b));
    const contorno = mesh(topo, topo.objects.mun, (a, b) => a === b);
    const projecao = geoMercator().fitExtent(
      [
        [12, 12],
        [largura - 12, altura - 12],
      ],
      { type: "FeatureCollection", features: municipios } as unknown as GeoPermissibleObjects,
    );
    const caminho = geoPath(projecao);
    return {
      projecao,
      caminho,
      municipios: municipios.map((m) => ({ id: Number(m.properties.cod), uf: m.properties.uf, d: caminho(m) ?? "", f: m })),
      fronteirasUf: caminho(fronteirasUf) ?? "",
      contorno: caminho(contorno) ?? "",
      comPoligono: new Set(municipios.map((m) => Number(m.properties.cod))),
    };
  }, [malha.data, largura, altura]);

  // Zoom/arraste com d3-zoom aplicado ao grupo (sem reprojetar os caminhos).
  useEffect(() => {
    const alvoSvg = svg.current;
    if (!alvoSvg || !grupo.current) return;
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 40])
      .translateExtent([
        [0, 0],
        [largura, altura],
      ])
      .on("zoom", (e) => {
        grupo.current?.setAttribute("transform", e.transform.toString());
        setEscalaZoom(e.transform.k);
        setHover(null);
      });
    comportamento.current = z;
    select(alvoSvg).call(z).on("dblclick.zoom", null);
    return () => {
      select(alvoSvg).on(".zoom", null);
    };
  }, [largura, altura, geo]);

  // Enquadra as UFs filtradas.
  useEffect(() => {
    if (!geo || !svg.current || !comportamento.current) return;
    const s = select(svg.current);
    if (!ufFoco.length) {
      s.transition().duration(350).call(comportamento.current.transform, zoomIdentity);
      return;
    }
    const alvo = geo.municipios.filter((m) => {
      const p = porId.get(m.id);
      return p && ufFoco.includes(p.uf);
    });
    if (!alvo.length) return;
    let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
    for (const m of alvo) {
      const [[a, b], [c, d]] = geo.caminho.bounds(m.f);
      x0 = Math.min(x0, a);
      y0 = Math.min(y0, b);
      x1 = Math.max(x1, c);
      y1 = Math.max(y1, d);
    }
    const k = Math.min(40, 0.88 / Math.max((x1 - x0) / largura, (y1 - y0) / altura));
    const t = zoomIdentity.translate(largura / 2, altura / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    s.transition().duration(450).call(comportamento.current.transform, t);
  }, [ufFoco, geo, porId, largura, altura]);

  const semPoligono = useMemo(
    () => (geo ? pontos.filter((p) => !geo.comPoligono.has(p.id)) : []),
    [geo, pontos],
  );

  const zoomPor = (fator: number) => {
    if (svg.current && comportamento.current)
      select(svg.current).transition().duration(200).call(comportamento.current.scaleBy, fator);
  };

  const sel = selecionado != null ? geo?.municipios.find((m) => m.id === selecionado) : undefined;
  const pontoHover = hover ? porId.get(hover.id) : undefined;

  return (
    <div ref={contêiner} className="relative w-full overflow-hidden rounded-control bg-[#fbfcfe]" style={{ height: altura }}>
      {malha.isError && (
        <p role="alert" className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-critico-ink">
          {(malha.error as Error).message}
        </p>
      )}
      {!geo && !malha.isError && <div className="absolute inset-0 animate-shimmer bg-sunken" aria-hidden />}
      <svg
        ref={svg}
        width={largura}
        height={altura}
        role="img"
        aria-label={`Mapa municipal do Brasil, camada ${ROTULO_CAMADA[camada]}. Use a lista ao lado para navegar pelo teclado.`}
        className="block cursor-grab touch-none active:cursor-grabbing"
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const id = Number((e.target as SVGElement).dataset?.id);
          onSelecionar(id && porId.has(id) ? id : null);
        }}
        onMouseMove={(e) => {
          const id = (e.target as SVGElement).dataset?.id;
          const caixa = contêiner.current?.getBoundingClientRect();
          if (!id || !caixa) return setHover(null);
          setHover({ id: Number(id), x: e.clientX - caixa.left, y: e.clientY - caixa.top });
        }}
      >
        <g ref={grupo}>
          {geo && <Municipios municipios={geo.municipios} porId={porId} cor={cor} />}
          {geo && (
            <>
              <path d={geo.fronteirasUf} fill="none" stroke="#3c4658" strokeOpacity={0.55} strokeWidth={0.9} vectorEffect="non-scaling-stroke" pointerEvents="none" />
              <path d={geo.contorno} fill="none" stroke="#3c4658" strokeOpacity={0.7} strokeWidth={1} vectorEffect="non-scaling-stroke" pointerEvents="none" />
              {semPoligono.map((p) => {
                const xy = geo.projecao([p.lon, p.lat]);
                if (!xy) return null;
                return (
                  <circle
                    key={p.id}
                    data-id={p.id}
                    cx={xy[0]}
                    cy={xy[1]}
                    r={3 / escalaZoom}
                    fill={cor(p)}
                    stroke="#3c4658"
                    strokeWidth={0.8}
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
              {hover && geo.municipios.find((m) => m.id === hover.id) && (
                <path
                  d={geo.municipios.find((m) => m.id === hover.id)!.d}
                  fill="none"
                  stroke="#172033"
                  strokeWidth={1.5}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
              )}
              {sel && (
                <path d={sel.d} fill="none" stroke="#172033" strokeWidth={2.5} vectorEffect="non-scaling-stroke" pointerEvents="none" />
              )}
            </>
          )}
        </g>
      </svg>

      <div className="absolute top-3 right-3 flex flex-col overflow-hidden rounded-control border border-line bg-surface shadow-[0_1px_2px_rgb(23_32_51/0.06)]">
        <BotaoMapa rotulo="Aproximar" onClick={() => zoomPor(1.6)}>
          <Plus className="size-4" />
        </BotaoMapa>
        <BotaoMapa rotulo="Afastar" onClick={() => zoomPor(1 / 1.6)}>
          <Minus className="size-4" />
        </BotaoMapa>
        <BotaoMapa
          rotulo="Enquadrar o Brasil"
          onClick={() => svg.current && comportamento.current && select(svg.current).transition().duration(350).call(comportamento.current.transform, zoomIdentity)}
        >
          <Maximize2 className="size-3.5" />
        </BotaoMapa>
      </div>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-56 rounded-control border border-line bg-surface px-3 py-2.5 text-xs shadow-float"
          style={{
            left: Math.min(hover.x + 14, largura - 236),
            top: Math.max(hover.y - 12, 8),
          }}
        >
          <MapTooltip ponto={pontoHover} camada={camada} />
        </div>
      )}
      {semPoligono.length > 0 && (
        <p className="absolute bottom-2 left-3 text-2xs text-muted">
          {semPoligono.length} município(s) sem polígono na malha aparecem como ponto na sede.
        </p>
      )}
    </div>
  );
}

function MapTooltip({ ponto, camada }: { ponto: Ponto | undefined; camada: Camada }) {
  if (!ponto) return <p className="text-muted">Sem notificações no recorte.</p>;
  return (
    <>
      <p className="mb-1.5 font-medium text-ink">
        {ponto.nome} <span className="font-normal text-muted">{ponto.uf}</span>
      </p>
      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
        {(["notificacoes", "confirmados", "hospitalizacoes", "obitos"] as const).map((k) => (
          <div key={k} className="contents">
            <dt className={k === camada ? "font-medium text-ink" : "text-muted"}>{ROTULO_CAMADA[k]}</dt>
            <dd className="num text-right text-ink">{fmtInt(ponto[k])}</dd>
          </div>
        ))}
        <dt className={camada === "score" ? "font-medium text-ink" : "text-muted"}>Score</dt>
        <dd className="num text-right text-ink">{ponto.score == null ? "—" : fmtDec(ponto.score)}</dd>
      </dl>
      <div className="mt-2">
        <CriticalityBadge nivel={ponto.nivel} />
      </div>
    </>
  );
}

function BotaoMapa({ rotulo, onClick, children }: { rotulo: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={rotulo}
      title={rotulo}
      onClick={onClick}
      className="flex size-8 items-center justify-center text-ink-2 not-last:border-b not-last:border-line hover:bg-canvas"
    >
      {children}
    </button>
  );
}

/** Camada de polígonos memorizada: não re-renderiza com hover. */
const Municipios = memo(function Municipios({
  municipios,
  porId,
  cor,
}: {
  municipios: { id: number; d: string }[];
  porId: Map<number, Ponto>;
  cor: (p: Ponto | undefined) => string;
}) {
  return (
    <g>
      {municipios.map((m) => (
        <path
          key={m.id}
          data-id={m.id}
          d={m.d}
          fill={cor(porId.get(m.id))}
          stroke="#ffffff"
          strokeWidth={0.35}
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </g>
  );
});

/**
 * O d3-geo usa anéis no sentido horário (esférico); a malha segue o RFC 7946
 * (anti-horário). Um polígono invertido cobre quase a esfera inteira (> 2π sr).
 */
function reorientar<T extends GeoPermissibleObjects>(f: T): T {
  if (geoArea(f) <= 2 * Math.PI) return f;
  const g = (f as unknown as { geometry: { type: string; coordinates: number[][][] | number[][][][] } }).geometry;
  if (g.type === "Polygon") (g.coordinates as number[][][]).forEach((anel) => anel.reverse());
  else (g.coordinates as number[][][][]).forEach((poligono) => poligono.forEach((anel) => anel.reverse()));
  return f;
}

export { RAMPA, SEM_NOTIFICACAO };
