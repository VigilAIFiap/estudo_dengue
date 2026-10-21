import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import PacientesPage from "@/app/pacientes/page";

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PacientesPage />
    </QueryClientProvider>,
  );
}

describe("formulário de acolhimento", () => {
  it("envia as respostas e confirma o protocolo recebido", async () => {
    const submit = vi.spyOn(api, "apiPost").mockResolvedValue({
      intake_id: 42,
      status: "PENDENTE",
    });

    renderForm();
    fireEvent.change(screen.getByLabelText("Faixa etária"), { target: { value: "20-39" } });
    fireEvent.change(screen.getByLabelText("Febre"), { target: { value: "SIM" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar para avaliação" }));

    await waitFor(() => expect(submit).toHaveBeenCalledOnce());
    expect(submit).toHaveBeenCalledWith(
      "/api/pacientes/avaliacao",
      expect.objectContaining({
        age_group: "20-39",
        fever: "SIM",
        sex: null,
        comorbidities: null,
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Registro 42 enviado à fila de avaliação do APEX.",
    );
    submit.mockRestore();
  });

  it("mantém uma mensagem clara quando o envio falha", async () => {
    const submit = vi.spyOn(api, "apiPost").mockRejectedValue(new Error("API indisponível"));
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Enviar para avaliação" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível registrar as informações.",
    );
    submit.mockRestore();
  });
});
