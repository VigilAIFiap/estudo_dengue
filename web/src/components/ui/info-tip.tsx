"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import type { ReactNode } from "react";

export function InfoTip({ children, rotulo = "Como é calculado" }: { children: ReactNode; rotulo?: string }) {
  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          aria-label={rotulo}
          className="inline-flex size-5 items-center justify-center rounded text-faint hover:text-ink-2"
        >
          <Info aria-hidden className="size-3.5" />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          align="start"
          sideOffset={6}
          className="z-50 max-w-72 rounded-lg bg-ink px-3 py-2 text-xs leading-[18px] text-white shadow-float"
        >
          {children}
          <Tooltip.Arrow className="fill-ink" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
