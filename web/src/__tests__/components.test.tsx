import { fireEvent, render, screen } from "@testing-library/react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { describe, expect, it, vi } from "vitest";
import { CriticalityBadge } from "@/components/ui/criticality-badge";
import { MetricBand } from "@/components/ui/metric-band";
import { ErrorState } from "@/components/ui/states";
import { AlertList } from "@/components/ui/alert-list";

describe("componentes", () => {
  it("nível de criticidade tem texto, não só cor", () => {
    render(<CriticalityBadge nivel="Crítico" />);
    expect(screen.getByText("Crítico")).toBeInTheDocument();
    render(<CriticalityBadge nivel={null} />);
    expect(screen.getByText("Sem score")).toBeInTheDocument();
  });

  it("faixa de indicadores mostra valor, variação e explicação acessível", () => {
    render(
      <Tooltip.Provider>
        <MetricBand
          metricas={[
            { id: "n", rotulo: "Notificações", valor: "309.957", variacao: -74.4, comparacaoRotulo: "vs. mesmo período de 2025", calculo: "Todos os registros" },
          ]}
        />
      </Tooltip.Provider>,
    );
    expect(screen.getByText("309.957")).toBeInTheDocument();
    expect(screen.getByText("−74,4%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Como é calculado: Notificações" })).toBeInTheDocument();
  });

  it("estado de erro mostra a mensagem e permite tentar de novo", () => {
    const tentar = vi.fn();
    render(<ErrorState erro={new Error("API fora do ar")} tentarNovamente={tentar} />);
    expect(screen.getByRole("alert")).toHaveTextContent("API fora do ar");
    fireEvent.click(screen.getByRole("button", { name: /tentar de novo/i }));
    expect(tentar).toHaveBeenCalledOnce();
  });

  it("alertas exibem o critério e informam quando nenhum foi disparado", () => {
    const { rerender } = render(
      <AlertList alertas={[{ id: "c", severidade: "Crítico", titulo: "1 município em nível crítico", criterio: "Score ≥ 50" }]} />,
    );
    expect(screen.getByText("Score ≥ 50")).toBeInTheDocument();
    expect(screen.getByText(/Severidade Crítico/)).toBeInTheDocument();
    rerender(<AlertList alertas={[]} />);
    expect(screen.getByText(/Nenhum critério de alerta/)).toBeInTheDocument();
  });
});
