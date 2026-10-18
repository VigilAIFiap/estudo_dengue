import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { AppShell } from "@/components/shell/app-shell";
import { Providers } from "@/components/shell/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Vigil — Vigilância da dengue", template: "%s — Vigil" },
  description: "Plataforma de inteligência epidemiológica da dengue para gestores públicos (SINAN).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={GeistSans.variable}>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
