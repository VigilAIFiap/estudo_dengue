import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function escolher(grupo: string, opcao: string) {
  const conjunto = screen.getByRole("group", { name: grupo });
  fireEvent.click(within(conjunto).getByRole("radio", { name: opcao }));
}

function preencherCompleto() {
  escolher("Faixa etária", "20 a 39");
  escolher("Sexo informado", "Feminino");
  escolher("Início dos sintomas", "Há 1 a 3 dias");
  escolher("Febre", "Sim");
  escolher("Dor de cabeça", "Sim");
  escolher("Dor muscular", "Não");
  escolher("Manchas ou erupção na pele", "Não");
  escolher("Náusea", "Não");
  escolher("Vômito", "Não");
  escolher("Gestação", "Não");
  escolher("Comorbidades", "Não");
}

describe("formulário de acolhimento", () => {
  it("envia as respostas e informa a aprovação automática", async () => {
    const submit = vi.spyOn(api, "apiPost").mockResolvedValue({
      intake_id: 42,
      status: "APROVADO",
      campos_faltantes: [],
      inconsistencias: [],
    });

    renderForm();
    preencherCompleto();
    fireEvent.click(screen.getByRole("button", { name: "Enviar triagem" }));

    await waitFor(() => expect(submit).toHaveBeenCalledOnce());
    expect(submit).toHaveBeenCalledWith(
      "/api/pacientes/avaliacao",
      expect.objectContaining({
        age_group: "20-39",
        sex: "F",
        fever: "SIM",
        muscle_pain: "NAO",
        comorbidities: "NAO",
      }),
    );
    const resultado = await screen.findByRole("status");
    expect(resultado).toHaveTextContent("Aprovado automaticamente");
    expect(resultado).toHaveTextContent("42");
    submit.mockRestore();
  });

  it("mostra o motivo quando o Oracle manda o registro para revisão", async () => {
    const submit = vi.spyOn(api, "apiPost").mockResolvedValue({
      intake_id: 43,
      status: "PENDENTE",
      campos_faltantes: ["FEBRE"],
      inconsistencias: ["GESTACAO_INCOMPATIVEL_COM_SEXO"],
    });

    renderForm();
    escolher("Faixa etária", "20 a 39");
    fireEvent.click(screen.getByRole("button", { name: "Enviar triagem" }));

    const resultado = await screen.findByRole("status");
    expect(resultado).toHaveTextContent("Enviado para revisão no APEX");
    expect(resultado).toHaveTextContent("Gestação informada para sexo masculino");
    expect(resultado).toHaveTextContent("Febre");
    submit.mockRestore();
  });

  it("atualiza a prévia da validação enquanto o formulário é preenchido", () => {
    renderForm();
    expect(screen.getByText("Irá para revisão no APEX")).toBeInTheDocument();
    expect(screen.getByText("0 de 11")).toBeInTheDocument();

    preencherCompleto();
    expect(screen.getByText("Pronto para aprovação automática")).toBeInTheDocument();
    expect(screen.getByText("11 de 11")).toBeInTheDocument();

    escolher("Gestação", "Sim");
    escolher("Sexo informado", "Masculino");
    expect(screen.getByText("Irá para revisão no APEX")).toBeInTheDocument();
    expect(screen.getByText("Gestação informada para sexo masculino")).toBeInTheDocument();
  });

  it("mantém uma mensagem clara quando o envio falha", async () => {
    const submit = vi.spyOn(api, "apiPost").mockRejectedValue(new Error("API indisponível"));
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Enviar triagem" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível registrar as informações.");
    submit.mockRestore();
  });

  it("explica quando o recebimento está desativado nesta instalação", async () => {
    const submit = vi
      .spyOn(api, "apiPost")
      .mockRejectedValue(new api.ApiError("Recebimento de formulários está desativado nesta instalação.", 503));
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Enviar triagem" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("está desativado nesta instalação");
    submit.mockRestore();
  });
});
