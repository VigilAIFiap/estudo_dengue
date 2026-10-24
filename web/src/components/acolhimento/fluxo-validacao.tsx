import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardList, Database, type LucideIcon } from "lucide-react";

type Cor = "primary" | "teal";

const COR: Record<Cor, { numero: string; fundo: string }> = {
  primary: { numero: "bg-primary text-white", fundo: "bg-primary-soft" },
  teal: { numero: "bg-teal text-white", fundo: "bg-teal-soft" },
};

function Etapa({ numero, cor, icone: Icone, titulo, texto }: { numero: number; cor: Cor; icone: LucideIcon; titulo: string; texto: string }) {
  return (
    <li className={`flex gap-3 rounded-control p-3.5 ${COR[cor].fundo}`}>
      <span className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${COR[cor].numero}`}>
        {numero}
      </span>
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <Icone aria-hidden className="size-4" /> {titulo}
        </p>
        <p className="mt-1 text-[13px] leading-5 text-ink-2">{texto}</p>
      </div>
    </li>
  );
}

function Seta() {
  return (
    <li aria-hidden className="hidden items-center justify-center text-faint lg:flex">
      <ArrowRight className="size-5" />
    </li>
  );
}

/** Como o registro percorre o sistema: do formulário à decisão do Oracle e à revisão no APEX. */
export function FluxoValidacao() {
  return (
    <section aria-label="Como funciona o acolhimento" className="rounded-panel border border-line bg-surface p-4">
      <ol className="grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1.15fr]">
        <Etapa
          numero={1}
          cor="primary"
          icone={ClipboardList}
          titulo="Triagem"
          texto="O profissional registra idade, sexo e sintomas. Não há nome, documento nem texto livre."
        />
        <Seta />
        <Etapa
          numero={2}
          cor="teal"
          icone={Database}
          titulo="Validação no Oracle"
          texto="As regras de completude e consistência rodam no banco, no instante do envio."
        />
        <Seta />
        <li className="flex flex-col gap-2">
          <p className="flex items-start gap-2 rounded-control bg-baixo-soft p-3 text-[13px] leading-5 text-ink-2">
            <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0 text-baixo-ink" />
            <span>
              <strong className="text-baixo-ink">Sem erros:</strong> aprovado automaticamente e enviado à base aprovada.
            </span>
          </p>
          <p className="flex items-start gap-2 rounded-control bg-medio-soft p-3 text-[13px] leading-5 text-ink-2">
            <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-medio-ink" />
            <span>
              <strong className="text-medio-ink">Com erros:</strong> fica na fila do Oracle APEX para um analista aprovar
              ou rejeitar, com histórico.
            </span>
          </p>
        </li>
      </ol>
      <p className="mt-3 text-xs text-muted">
        <span className="font-medium">Fonte:</span> formulário de triagem sem identificação direta, gravado no Oracle e
        revisado no Oracle APEX.
      </p>
    </section>
  );
}
