"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: ReactNode }) {
  const [cliente] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000,
            refetchOnWindowFocus: false,
            // Erros 4xx são definitivos; só falhas de rede/servidor tentam de novo.
            retry: (tentativas, erro) =>
              tentativas < 2 && !(erro instanceof ApiError && erro.status >= 400 && erro.status < 500),
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={cliente}>
      <Tooltip.Provider>{children}</Tooltip.Provider>
    </QueryClientProvider>
  );
}
