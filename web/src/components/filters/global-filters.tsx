"use client";

import * as Popover from "@radix-ui/react-popover";
import { CalendarRange, ChevronDown, MapPin, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { gatilho, MultiSelect } from "@/components/ui/multi-select";
import { MunicipioCombobox } from "@/components/ui/municipio-combobox";
import { intervaloAnoEpi, limitar } from "@/lib/epi";
import { contarAtivos } from "@/lib/filters";
import { fmtData } from "@/lib/format";
import { useFiltrosResolvidos, useMunicipio } from "@/lib/queries";
import { useFiltros } from "@/lib/use-filtros";

type Props = {
  /** Período: não se aplica nesta página (desabilita). Município: como a página o usa (só nota). */
  ignorados?: { periodo?: string; municipio?: string };
  className?: string;
};

export function GlobalFilters({ ignorados, className }: Props) {
  const { filtros, definir, limpar } = useFiltros();
  const { meta, inicio, fim } = useFiltrosResolvidos();
  const ativos = contarAtivos(filtros);
  const m = meta.data;

  return (
    <div className={cn("mb-5 flex flex-col gap-2", className)}>
      <div role="group" aria-label="Filtros globais" className="flex flex-wrap items-center gap-2">
        <PeriodoFiltro desabilitado={!!ignorados?.periodo} />
        {m && (
          <MultiSelect
            rotulo="UF"
            buscavel
            opcoes={m.ufs.map((u) => ({ valor: u.sigla, rotulo: u.nome, detalhe: u.sigla }))}
            selecionados={filtros.uf}
            onChange={(uf) => definir({ uf, municipio: undefined })}
            resumo={filtros.uf.length ? (filtros.uf.length <= 3 ? filtros.uf.join(", ") : `${filtros.uf.length} UFs`) : "Brasil"}
          />
        )}
        <MunicipioFiltro />
        {m && (
          <MultiSelect
            rotulo="Classificação"
            largura={320}
            opcoes={m.classificacoes.map((c) => ({
              valor: c.codigo,
              rotulo: c.rotulo,
              detalhe: m.confirmados_codigos.includes(c.codigo) ? "confirmado" : undefined,
            }))}
            selecionados={filtros.classificacao}
            onChange={(classificacao) => definir({ classificacao })}
            resumo={
              filtros.classificacao.length
                ? filtros.classificacao.length === 1
                  ? (m.classificacoes.find((c) => c.codigo === filtros.classificacao[0])?.rotulo ?? "1")
                  : `${filtros.classificacao.length} selecionadas`
                : "Todas"
            }
          />
        )}
        {ativos > 0 && (
          <Button variante="fantasma" onClick={limpar}>
            <X aria-hidden className="size-3.5" /> Limpar filtros
          </Button>
        )}
      </div>
      <p className="text-xs leading-5 text-muted" aria-live="polite">
        {inicio && fim && !ignorados?.periodo && (
          <>
            Período de <span className="num text-ink-2">{fmtData(inicio)}</span> a{" "}
            <span className="num text-ink-2">{fmtData(fim)}</span>
            {!filtros.inicio && !filtros.fim && " (padrão: ano epidemiológico mais recente)"}.
          </>
        )}
        {ignorados?.periodo && <>{ignorados.periodo} </>}
        {ignorados?.municipio && filtros.municipio && <> {ignorados.municipio}</>}
      </p>
    </div>
  );
}

function PeriodoFiltro({ desabilitado }: { desabilitado: boolean }) {
  const { filtros, definir } = useFiltros();
  const { meta, inicio, fim } = useFiltrosResolvidos();
  const [aberto, setAberto] = useState(false);
  const [rascunho, setRascunho] = useState({ inicio: "", fim: "" });
  const m = meta.data;
  if (!m) return <span className="h-8 w-44 animate-shimmer rounded-control bg-sunken" aria-hidden />;

  const anoFim = Number(m.cobertura_fim.slice(0, 4));
  const presets = [
    { rotulo: `Ano epidemiológico ${anoFim}`, nota: "até a última notificação", ...limitar(intervaloAnoEpi(anoFim), m.cobertura_inicio, m.cobertura_fim) },
    { rotulo: `Ano epidemiológico ${anoFim - 1}`, nota: "SE 1 a SE 53", ...limitar(intervaloAnoEpi(anoFim - 1), m.cobertura_inicio, m.cobertura_fim) },
    { rotulo: "Toda a base", nota: `${fmtData(m.cobertura_inicio)} a ${fmtData(m.cobertura_fim)}`, inicio: m.cobertura_inicio, fim: m.cobertura_fim },
  ];
  const resumo = presets.find((p) => p.inicio === inicio && p.fim === fim)?.rotulo ?? `${fmtData(inicio!)} – ${fmtData(fim!)}`;
  const valido = rascunho.inicio && rascunho.fim && rascunho.inicio <= rascunho.fim;

  return (
    <Popover.Root
      open={aberto}
      onOpenChange={(a) => {
        setAberto(a);
        if (a) setRascunho({ inicio: inicio!, fim: fim! });
      }}
    >
      <Popover.Trigger asChild disabled={desabilitado}>
        <button type="button" className={cn(gatilho(!!(filtros.inicio || filtros.fim)), desabilitado && "opacity-50")}>
          <CalendarRange aria-hidden className="size-3.5 text-faint" />
          <span className="text-muted">Período</span>
          <span className="font-medium text-ink">{resumo}</span>
          <ChevronDown aria-hidden className="size-3.5 text-faint" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={6} className="z-50 w-[320px] rounded-control border border-line bg-surface p-2 shadow-float">
          <ul className="flex flex-col">
            {presets.map((p) => (
              <li key={p.rotulo}>
                <button
                  type="button"
                  onClick={() => {
                    definir({ inicio: p.inicio, fim: p.fim });
                    setAberto(false);
                  }}
                  className={cn(
                    "flex w-full items-baseline justify-between gap-3 rounded-md px-2.5 py-2 text-left text-sm hover:bg-canvas",
                    p.inicio === inicio && p.fim === fim && "bg-primary-soft",
                  )}
                >
                  <span className="text-ink">{p.rotulo}</span>
                  <span className="text-xs text-muted">{p.nota}</span>
                </button>
              </li>
            ))}
          </ul>
          <form
            className="mt-2 border-t border-line px-1.5 pt-3 pb-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (!valido) return;
              definir({ inicio: rascunho.inicio, fim: rascunho.fim });
              setAberto(false);
            }}
          >
            <fieldset className="grid grid-cols-2 gap-2">
              <legend className="mb-2 text-xs text-muted">Intervalo personalizado</legend>
              {(["inicio", "fim"] as const).map((campo) => (
                <label key={campo} className="flex flex-col gap-1 text-xs text-muted">
                  {campo === "inicio" ? "De" : "Até"}
                  <input
                    type="date"
                    required
                    min={m.cobertura_inicio}
                    max={m.cobertura_fim}
                    value={rascunho[campo]}
                    onChange={(e) => setRascunho((r) => ({ ...r, [campo]: e.target.value }))}
                    className="num h-8 rounded-md border border-line px-2 text-sm text-ink"
                  />
                </label>
              ))}
            </fieldset>
            {rascunho.inicio && rascunho.fim && !valido && (
              <p className="mt-2 text-xs text-critico-ink">A data inicial deve ser anterior à final.</p>
            )}
            <div className="mt-3 flex justify-end gap-2">
              {(filtros.inicio || filtros.fim) && (
                <Button
                  variante="fantasma"
                  onClick={() => {
                    definir({ inicio: undefined, fim: undefined });
                    setAberto(false);
                  }}
                >
                  Voltar ao padrão
                </Button>
              )}
              <Button variante="primario" type="submit" disabled={!valido}>
                Aplicar período
              </Button>
            </div>
          </form>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function MunicipioFiltro() {
  const { filtros, definir } = useFiltros();
  const [aberto, setAberto] = useState(false);
  const detalhe = useMunicipio(filtros.municipio);
  const nome = filtros.municipio ? (detalhe.data ? `${detalhe.data.nome} (${detalhe.data.uf})` : "…") : "Todos";

  return (
    <div className="inline-flex items-center">
      <Popover.Root open={aberto} onOpenChange={setAberto}>
        <Popover.Trigger asChild>
          <button type="button" className={cn(gatilho(!!filtros.municipio), filtros.municipio && "rounded-r-none border-r-0")}>
            <MapPin aria-hidden className="size-3.5 text-faint" />
            <span className="text-muted">Município</span>
            <span className="max-w-44 truncate font-medium text-ink">{nome}</span>
            <ChevronDown aria-hidden className="size-3.5 text-faint" />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content align="start" sideOffset={6} className="z-50 w-[300px] rounded-control border border-line bg-surface p-2 shadow-float">
            <MunicipioCombobox
              autoFocus
              onSelecionar={(mun) => {
                definir({ municipio: mun.id_municip });
                setAberto(false);
              }}
            />
            <p className="mt-2 px-1 text-xs leading-4 text-muted">
              Filtra indicadores e séries. O ranking e o mapa continuam mostrando todos os municípios, com o selecionado em destaque.
            </p>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      {filtros.municipio && (
        <button
          type="button"
          aria-label="Remover filtro de município"
          onClick={() => definir({ municipio: undefined })}
          className="inline-flex h-8 items-center rounded-r-control border border-primary/40 bg-primary-soft px-1.5 text-primary-ink hover:bg-primary/15"
        >
          <X aria-hidden className="size-3.5" />
        </button>
      )}
    </div>
  );
}
