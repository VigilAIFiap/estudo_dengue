"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Database, Download, MessageSquareText } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { IntegrationNotice } from "@/components/ui/integration-notice";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { apiPost, type Schemas } from "@/lib/api";
import { useAssistStatus } from "@/lib/queries";

type Mensagem = Schemas["MensagemAssist"] & { consultas?: Schemas["ConsultaFerramenta"][] };

const SUGESTOES = [
  "Quais os 5 municípios com maior score de criticidade em 2026?",
  "Como as notificações de 2026 se comparam às mesmas semanas de 2025?",
  "Resuma a situação de Goiânia no ano epidemiológico mais recente.",
  "Quais UFs concentram mais óbitos pelo agravo?",
];

const ROTULO_FERRAMENTA: Record<string, string> = {
  visao_geral: "Visão geral",
  ranking_municipios: "Ranking de municípios",
  serie_temporal: "Série temporal",
  municipio: "Município",
};

export default function AssistentePage() {
  const status = useAssistStatus();
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState("");
  const fim = useRef<HTMLDivElement>(null);
  const configurado = !!status.data?.configurado;

  const enviar = useMutation({
    mutationFn: (historico: Mensagem[]) =>
      apiPost<Schemas["RespostaAssist"]>("/api/assist", {
        mensagens: historico.map(({ papel, texto }) => ({ papel, texto })),
      }),
    onSuccess: (r) => setMensagens((m) => [...m, { papel: "assistente", texto: r.texto, consultas: r.consultas }]),
  });

  useEffect(() => fim.current?.scrollIntoView({ block: "end", behavior: "smooth" }), [mensagens, enviar.isPending]);

  const perguntar = (pergunta: string) => {
    const t = pergunta.trim();
    if (!t || enviar.isPending || !configurado) return;
    const historico: Mensagem[] = [...mensagens, { papel: "usuario", texto: t }];
    setMensagens(historico);
    setTexto("");
    enviar.mutate(historico);
  };

  const baixar = () => {
    const md = mensagens
      .map((m) => `**${m.papel === "usuario" ? "Pergunta" : "Vigil Assist"}**\n\n${m.texto}${m.consultas?.length ? `\n\n_Consultas: ${m.consultas.map((c) => `${c.ferramenta} ${JSON.stringify(c.parametros)}`).join("; ")}_` : ""}`)
      .join("\n\n---\n\n");
    const url = URL.createObjectURL(new Blob([`# Conversa com o Vigil Assist\n\n${md}\n`], { type: "text/markdown" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "vigil-assist-conversa.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader
        titulo="Vigil Assist"
        descricao="Perguntas em linguagem natural respondidas com consultas à API analítica. Cada resposta lista as consultas que a embasaram."
        acoes={
          mensagens.length > 0 && (
            <Button onClick={baixar}>
              <Download aria-hidden className="size-3.5" /> Baixar conversa
            </Button>
          )
        }
      />

      {status.isError && <ErrorState erro={status.error} tentarNovamente={() => status.refetch()} />}
      {status.isLoading && <LoadingState altura={80} />}
      {status.data && !configurado && (
        <IntegrationNotice titulo="Nenhum provedor de IA configurado">
          <p>
            A interface e as ferramentas de consulta estão prontas, mas não há chave de API no servidor. Defina{" "}
            <code className="rounded bg-white/70 px-1 text-[13px]">ANTHROPIC_API_KEY</code> no arquivo .env da API e reinicie o uvicorn.
            Sem isso, o assistente não responde: não existem respostas prontas simuladas.
          </p>
        </IntegrationNotice>
      )}

      <section aria-label="Conversa" className="flex min-h-[520px] flex-col rounded-panel border border-line bg-surface">
        <div className="flex-1 overflow-y-auto px-5 py-5" aria-live="polite">
          {!mensagens.length ? (
            <div className="mx-auto flex max-w-xl flex-col items-center gap-4 py-10 text-center">
              <span className="flex size-10 items-center justify-center rounded-control bg-primary-soft">
                <MessageSquareText aria-hidden className="size-5 text-primary" />
              </span>
              <div>
                <h2 className="text-[15px] font-semibold text-ink">Pergunte sobre os indicadores</h2>
                <p className="mt-1 text-[13px] leading-5 text-muted">
                  O assistente consulta {status.data?.ferramentas.map((f) => ROTULO_FERRAMENTA[f] ?? f).join(", ").toLowerCase()}. A conversa fica
                  só nesta aba e não é salva.
                </p>
              </div>
              <ul className="grid w-full gap-2 sm:grid-cols-2">
                {SUGESTOES.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      disabled={!configurado}
                      onClick={() => perguntar(s)}
                      className="h-full w-full rounded-control border border-line px-3 py-2.5 text-left text-[13px] leading-5 text-ink-2 hover:border-line-strong hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <ol className="mx-auto flex max-w-3xl flex-col gap-5">
              {mensagens.map((m, i) => (
                <li key={i} className={cn("flex flex-col gap-1.5", m.papel === "usuario" ? "items-end" : "items-start")}>
                  <span className="text-xs text-muted">{m.papel === "usuario" ? "Você" : "Vigil Assist"}</span>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-panel px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap",
                      m.papel === "usuario" ? "bg-primary text-white" : "border border-line bg-canvas text-ink",
                    )}
                  >
                    {m.texto}
                  </div>
                  {!!m.consultas?.length && (
                    <ul className="flex flex-wrap gap-1.5" aria-label="Consultas realizadas">
                      {m.consultas.map((c, j) => (
                        <li
                          key={j}
                          title={JSON.stringify(c.parametros)}
                          className="inline-flex items-center gap-1 rounded-chip bg-teal-soft px-2 py-0.5 text-xs text-[#0b6f6d]"
                        >
                          <Database aria-hidden className="size-3" />
                          {ROTULO_FERRAMENTA[c.ferramenta] ?? c.ferramenta}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
              {enviar.isPending && (
                <li className="flex items-center gap-2 text-[13px] text-muted" role="status">
                  <span className="size-2 animate-shimmer rounded-full bg-primary" /> Consultando os dados…
                </li>
              )}
              {enviar.isError && (
                <li>
                  <ErrorState erro={enviar.error} tentarNovamente={() => enviar.mutate(mensagens)} />
                </li>
              )}
            </ol>
          )}
          <div ref={fim} />
        </div>
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            perguntar(texto);
          }}
          className="border-t border-line p-3"
        >
          <label className="flex items-end gap-2 rounded-control border border-line bg-surface px-3 py-2 focus-within:border-primary/50">
            <span className="sr-only">Sua pergunta</span>
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  perguntar(texto);
                }
              }}
              rows={1}
              disabled={!configurado}
              placeholder={configurado ? "Pergunte sobre notificações, municípios ou tendências" : "Configure um provedor de IA para conversar"}
              className="max-h-40 min-h-6 flex-1 resize-none bg-transparent text-sm leading-6 text-ink outline-none placeholder:text-faint disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              aria-label="Enviar pergunta"
              disabled={!configurado || !texto.trim() || enviar.isPending}
              className="flex size-8 shrink-0 items-center justify-center rounded-control bg-primary text-white disabled:opacity-40"
            >
              <ArrowUp aria-hidden className="size-4" />
            </button>
          </label>
          <p className="mt-1.5 px-1 text-2xs text-muted">
            Respostas se limitam aos dados consultados. Não substituem análise técnica nem orientação clínica.
          </p>
        </form>
      </section>
    </>
  );
}
