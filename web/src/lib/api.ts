import type { components } from "./api-schema";

export type Schemas = components["schemas"];

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function tratar<T>(resposta: Response): Promise<T> {
  if (resposta.ok) return (await resposta.json()) as T;
  let detalhe = `A API respondeu ${resposta.status}.`;
  try {
    const corpo = (await resposta.json()) as { detail?: unknown };
    if (typeof corpo.detail === "string") detalhe = corpo.detail;
  } catch {
    // Corpo não é JSON: com 5xx, quem respondeu foi o proxy do Next sem alcançar a API.
    if (resposta.status >= 500) detalhe = SEM_API;
  }
  throw new ApiError(detalhe, resposta.status);
}

const SEM_API =
  "Não foi possível conectar à API analítica. Verifique se ela está em execução (uvicorn api.main:app --port 8000).";

function falhaDeRede(erro: unknown): never {
  if (erro instanceof DOMException && erro.name === "AbortError") throw erro;
  throw new ApiError(SEM_API, 0);
}

export async function apiGet<T>(caminho: string, params?: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const url = params && params.size ? `${caminho}?${params}` : caminho;
  const resposta = await fetch(url, { signal, headers: { Accept: "application/json" } }).catch(falhaDeRede);
  return tratar<T>(resposta);
}

export async function apiPost<T>(caminho: string, corpo: unknown, signal?: AbortSignal): Promise<T> {
  const resposta = await fetch(caminho, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(corpo),
  }).catch(falhaDeRede);
  return tratar<T>(resposta);
}
