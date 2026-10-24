"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { Suspense, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { DataFreshnessIndicator } from "@/components/ui/freshness";
import { FonteStrip } from "./fonte-strip";
import { AppSidebar, NavList } from "./app-sidebar";
import { BrandMark } from "./brand";
import { ApiGate } from "./api-gate";
import { MunicipioSearch } from "./municipio-search";

const CHAVE = "vigil:menu-recolhido";
const semAssinatura = () => () => {};

/**
 * Todo o conteúdo depende da API e da URL do navegador; renderizá-lo só no
 * cliente evita divergência de hidratação quando a consulta termina antes.
 */
function useMontado() {
  return useSyncExternalStore(semAssinatura, () => true, () => false);
}

export function AppShell({ children }: { children: ReactNode }) {
  const [recolhida, setRecolhida] = useState(false);
  const [menuAberto, setMenuAberto] = useState(false);
  const montado = useMontado();

  useEffect(() => {
    try {
      // Preferência local do visitante; sem armazenamento, o menu fica expandido.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRecolhida(localStorage.getItem(CHAVE) === "1");
    } catch {}
  }, []);

  const alternar = () =>
    setRecolhida((r) => {
      try {
        localStorage.setItem(CHAVE, r ? "0" : "1");
      } catch {}
      return !r;
    });

  return (
    <div className="flex min-h-dvh">
      <a
        href="#conteudo"
        className="sr-only z-50 rounded-control bg-ink px-3 py-2 text-sm text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Pular para o conteúdo
      </a>
      <Suspense>
        <AppSidebar recolhida={recolhida} alternar={alternar} />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur-sm md:px-6">
          <Dialog.Root open={menuAberto} onOpenChange={setMenuAberto}>
            <Dialog.Trigger asChild>
              <button
                type="button"
                aria-label="Abrir menu"
                className="-ml-1 inline-flex size-9 items-center justify-center rounded-control text-ink-2 hover:bg-sunken md:hidden"
              >
                <Menu aria-hidden className="size-5" />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/30" />
              <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-surface shadow-float">
                <div className="flex h-14 items-center justify-between border-b border-line px-4">
                  <Dialog.Title className="flex items-center gap-2.5 text-[15px] font-semibold">
                    <BrandMark /> Vigil
                  </Dialog.Title>
                  <Dialog.Close aria-label="Fechar menu" className="rounded-control p-1.5 text-muted hover:bg-sunken">
                    <X aria-hidden className="size-5" />
                  </Dialog.Close>
                </div>
                <Dialog.Description className="sr-only">Navegação principal</Dialog.Description>
                <div className="flex-1 overflow-y-auto p-3">
                  <Suspense>
                    <NavList aoNavegar={() => setMenuAberto(false)} />
                  </Suspense>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <div className="min-w-0 flex-1">
            <Suspense>
              <MunicipioSearch />
            </Suspense>
          </div>
          <DataFreshnessIndicator />
        </header>
        <main id="conteudo" className="mx-auto w-full max-w-[1480px] flex-1 px-4 pt-6 pb-12 md:px-6">
          {montado ? (
            <ApiGate>
              <Suspense>
                <FonteStrip />
                {children}
              </Suspense>
            </ApiGate>
          ) : (
            <div aria-busy className="h-40" />
          )}
        </main>
      </div>
    </div>
  );
}
