"""Modo apresentação: verifica o ambiente e inicia a API e o front compilado.

Uso, na raiz do projeto, com o venv ativo:

    python scripts/demo.py                 # verifica, inicia tudo e abre o navegador
    python scripts/demo.py --verificar     # só verifica o ambiente, sem iniciar nada
    python scripts/demo.py --build         # refaz o build do front antes de iniciar
    python scripts/demo.py --sem-navegador # não abre o navegador
    python scripts/demo.py --sem-aquecer   # não pré-calcula a previsão

Pare tudo com Ctrl+C. Os painéis funcionam sem internet (modo CSV); o Acolhimento e o Oracle APEX
precisam de conexão com o Oracle na nuvem.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoExpirou
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / "web"
PORTA_API = 8000
PORTA_FRONT = 3000
URL_FRONT = f"http://localhost:{PORTA_FRONT}"
ARQUIVOS_ANUAIS = ("DENGBR23.csv", "DENGBR24.csv", "DENGBR25.csv", "DENGBR26.csv")
CHAVES_ORACLE = ("DB_USER", "DB_PASSWORD", "DB_DSN", "WALLET_DIR", "WALLET_PASSWORD")
VALORES_VISIVEIS = {
    "DB_USER", "DB_DSN", "DATA_SOURCE", "TRIAGE_FORM_ENABLED", "DENGUE_MUNICIPIO_BASE",
    "VIGIL_DQ_SCHEMA", "ORACLE_API_TABLE", "API_CORS_ORIGINS",
}


@dataclass
class Item:
    nome: str
    ok: bool
    detalhe: str
    critico: bool = True  # se falhar, a demonstração não deve começar


# --------------------------------------------------------------------------- configuração

def carregar_env(raiz: Path = RAIZ) -> dict[str, str]:
    """Lê o .env da raiz (sem alterar o ambiente do processo)."""
    arquivo = raiz / ".env"
    if not arquivo.exists():
        return {}
    from dotenv import dotenv_values

    return {k: v for k, v in dotenv_values(arquivo).items() if v is not None}


def verdadeiro(valor: str | None) -> bool:
    return (valor or "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def pasta_dados(env: dict[str, str], raiz: Path = RAIZ) -> Path:
    return Path(env.get("DENGUE_DATA_DIR") or raiz / "dados" / "raw")


# --------------------------------------------------------------------------- verificações

def verificar_env(env: dict[str, str], raiz: Path = RAIZ) -> list[Item]:
    if not (raiz / ".env").exists():
        return [Item(".env", False, "Arquivo .env não encontrado na raiz. Copie o .env.example e preencha.")]
    itens = [Item(".env", True, "encontrado")]
    fonte = (env.get("DATA_SOURCE") or "csv").strip().lower()
    itens.append(Item("Fonte dos dados", fonte in {"csv", "oracle"}, f"DATA_SOURCE={fonte}"))
    if verdadeiro(env.get("TRIAGE_FORM_ENABLED")):
        itens.append(Item("Formulário de acolhimento", True, "ligado (TRIAGE_FORM_ENABLED=true)", critico=False))
    else:
        itens.append(Item(
            "Formulário de acolhimento", False,
            "desligado: a tela de Acolhimento vai avisar que o recebimento está desativado. "
            "Para demonstrar, use TRIAGE_FORM_ENABLED=true no .env.",
            critico=False,
        ))
    return itens


def verificar_valores_repetidos(env: dict[str, str]) -> list[Item]:
    """Erro comum ao copiar: DB_DSN=DB_DSN=valor (o nome da variável repetido dentro do valor)."""
    erradas = [k for k in CHAVES_ORACLE if env.get(k, "").strip().startswith(f"{k}=")]
    if not erradas:
        return []
    obrigatorio = (env.get("DATA_SOURCE") or "csv").strip().lower() == "oracle"
    return [Item(
        "Valores do .env", False,
        f"o valor de {', '.join(erradas)} repete o nome da variável (por exemplo, DB_DSN=DB_DSN=alias). "
        "Deixe só o valor depois do primeiro '='.",
        critico=obrigatorio,
    )]


def aplicar_env(env: dict[str, str], ambiente: dict[str, str] | None = None) -> list[Item]:
    """Faz o .env valer nesta execução, mesmo que o Windows ou a sessão do PowerShell definam outros valores.

    O load_dotenv() não sobrescreve variáveis já existentes; sem isto, um TRIAGE_FORM_ENABLED=false ou um
    DB_USER=ADMIN esquecidos na sessão venceriam o .env e os processos filhos os herdariam.
    """
    ambiente = os.environ if ambiente is None else ambiente
    conflitos = [chave for chave, valor in env.items() if chave in ambiente and ambiente[chave] != valor]
    antigos_visiveis = {chave: ambiente[chave] for chave in conflitos if chave in VALORES_VISIVEIS}
    ambiente.update(env)
    if not conflitos:
        return []
    detalhes = []
    for chave in conflitos:
        if chave in VALORES_VISIVEIS:
            detalhes.append(f'{chave} (sessão: "{antigos_visiveis.get(chave, "")}"; .env: "{env[chave]}")')
        else:
            detalhes.append(f"{chave} (valor diferente do .env)")
    return [Item(
        "Variáveis da sessão", True,
        "o demo usa o .env e ignorou valores diferentes da sessão ou do Windows em: " + "; ".join(detalhes)
        + ". Para limpá-los de vez: Remove-Item Env:NOME e, se vierem do Windows, "
        "[Environment]::SetEnvironmentVariable('NOME', $null, 'User')",
        critico=False,
    )]


def contar_avisos(itens: list[Item]) -> int:
    """Itens que falharam sem impedir a demonstração (o resto funciona, mas algo não vai funcionar)."""
    return sum(1 for item in itens if not item.ok and not item.critico)


def verificar_dados_csv(env: dict[str, str], raiz: Path = RAIZ) -> list[Item]:
    if (env.get("DATA_SOURCE") or "csv").strip().lower() != "csv":
        return []
    pasta = pasta_dados(env, raiz)
    faltando = [nome for nome in ARQUIVOS_ANUAIS if not (pasta / nome).exists()]
    if faltando:
        return [Item("Arquivos do SINAN", False, f"faltam em {pasta}: {', '.join(faltando)}")]
    itens = [Item("Arquivos do SINAN", True, f"{len(ARQUIVOS_ANUAIS)} arquivos anuais em {pasta}")]
    if (env.get("DENGUE_MUNICIPIO_BASE") or "").strip().lower() == "residencia":
        sem_coluna = []
        for nome in ARQUIVOS_ANUAIS:
            with open(pasta / nome, encoding="latin-1") as arquivo:
                cabecalho = arquivo.readline().strip().split(",")
            if "ID_MN_RESI" not in cabecalho:
                sem_coluna.append(nome)
        itens.append(Item(
            "Município de residência", not sem_coluna,
            "coluna ID_MN_RESI presente em todos os arquivos" if not sem_coluna
            else f"sem ID_MN_RESI em: {', '.join(sem_coluna)}",
        ))
    return itens


def versao_node(texto: str) -> tuple[int, int]:
    """'v22.1.0' -> (22, 1). Retorna (0, 0) se não reconhecer."""
    partes = texto.strip().lstrip("v").split(".")
    try:
        return int(partes[0]), int(partes[1]) if len(partes) > 1 else 0
    except (ValueError, IndexError):
        return 0, 0


def verificar_ferramentas(raiz: Path = RAIZ) -> list[Item]:
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        return [Item("Node.js e npm", False, "não encontrados no PATH. Instale o Node.js 20.9 ou superior.")]
    saida = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    maior, menor = versao_node(saida)
    itens = [Item("Node.js", (maior, menor) >= (20, 9), f"{saida.strip()} (mínimo 20.9)")]
    itens.append(Item(
        "Dependências do front", (raiz / "web" / "node_modules").exists(),
        "instaladas" if (raiz / "web" / "node_modules").exists() else "rode: cd web; npm ci",
    ))
    return itens


def build_existe(raiz: Path = RAIZ) -> bool:
    return (raiz / "web" / ".next" / "BUILD_ID").exists()


def porta_em_uso(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def verificar_portas() -> list[Item]:
    ocupadas = [p for p in (PORTA_API, PORTA_FRONT) if porta_em_uso(p)]
    if ocupadas:
        return [Item("Portas 8000 e 3000", False,
                     f"em uso: {', '.join(map(str, ocupadas))}. Feche o outro terminal ou programa que as usa.")]
    return [Item("Portas 8000 e 3000", True, "livres")]


def avaliar_conexao(usuario: str, esquema: str, validos: int) -> tuple[bool, str]:
    """Decide se a conexão serve para o Acolhimento e explica o motivo quando não serve."""
    if usuario != "VIGIL_APEX" or esquema != "VIGIL_APEX":
        return False, (
            f"conectado como {usuario} (schema {esquema}), mas o esperado é VIGIL_APEX. Confira DB_USER no .env e se "
            "há DB_USER/DB_PASSWORD definidos na sessão do PowerShell: eles vencem o .env"
        )
    if validos < 5:
        return False, (
            f"só {validos} dos objetos da triagem estão válidos no Oracle (esperado: 5). "
            "Rode o migrate_triage_approval.sql como VIGIL_APEX"
        )
    return True, "conectado ao schema VIGIL_APEX com os objetos da triagem válidos"


def _consultar_oracle() -> tuple[bool, str]:
    sys.path.insert(0, str(RAIZ))
    from src.con_db import con_sql

    conexao, mensagem = con_sql()
    if conexao is None:
        return False, mensagem
    try:
        with conexao.cursor() as cursor:
            cursor.execute(
                "SELECT SYS_CONTEXT('USERENV', 'SESSION_USER'), SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL"
            )
            usuario, esquema = cursor.fetchone()
            cursor.execute(
                "SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME IN "
                "('VIGIL_TRIAGE_INTAKE', 'VIGIL_TRIAGE_APROVADO', 'VIGIL_TRIAGE_REVIEW', 'VIGIL_TRIAGE_REVIEW_QUEUE') "
                "AND STATUS = 'VALID'"
            )
            validos = int(cursor.fetchone()[0])
        return avaliar_conexao(usuario, esquema, validos)
    finally:
        conexao.close()


def verificar_oracle(env: dict[str, str], tempo: int = 25) -> Item:
    """Conecta ao Oracle com limite de tempo, para não travar quando não há internet."""
    obrigatorio = (env.get("DATA_SOURCE") or "csv").strip().lower() == "oracle"
    with ThreadPoolExecutor(max_workers=1) as pool:
        futuro = pool.submit(_consultar_oracle)
        try:
            ok, detalhe = futuro.result(timeout=tempo)
        except FuturoExpirou:
            ok, detalhe = False, f"sem resposta em {tempo}s (verifique a internet e a wallet)"
        except Exception as erro:  # noqa: BLE001 — qualquer falha vira aviso legível
            ok, detalhe = False, f"{type(erro).__name__}: {erro}"
    if not ok and not obrigatorio:
        detalhe += ". Os painéis funcionam, mas o Acolhimento não vai gravar."
    return Item("Oracle (Acolhimento e APEX)", ok, detalhe, critico=obrigatorio)


def verificar_tudo(env: dict[str, str], com_oracle: bool = True, raiz: Path = RAIZ) -> list[Item]:
    itens = verificar_env(env, raiz)
    if not (raiz / ".env").exists():
        return itens
    itens += verificar_valores_repetidos(env)
    itens += verificar_dados_csv(env, raiz)
    itens += verificar_ferramentas(raiz)
    itens += verificar_portas()
    if com_oracle:
        itens.append(verificar_oracle(env))
    return itens


def imprimir(itens: list[Item]) -> bool:
    """Mostra o resultado e devolve True se nenhum item crítico falhou."""
    tudo_certo = True
    print("\nVerificação do ambiente")
    print("-" * 60)
    for item in itens:
        marca = "[ok]      " if item.ok else ("[ERRO]    " if item.critico else "[ATENCAO] ")
        print(f"{marca}{item.nome}: {item.detalhe}")
        if not item.ok and item.critico:
            tudo_certo = False
    print("-" * 60)
    return tudo_certo


# --------------------------------------------------------------------------- execução

def esperar_url(url: str, limite: float, intervalo: float = 1.0) -> bool:
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        try:
            with urllib.request.urlopen(url, timeout=3) as resposta:
                if resposta.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(intervalo)
    return False


def aquecer_previsao(url: str, limite: float = 900) -> tuple[bool, float]:
    """Pede a previsão uma vez, direto à API, para que ela fique em cache antes de a tela ser aberta.

    O ajuste do SARIMA leva de dezenas de segundos a minutos; passando pelo front, o proxy do Next
    desiste após cerca de 30 segundos. Devolve (deu certo, segundos gastos).
    """
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=limite) as resposta:
            return resposta.status == 200, time.monotonic() - inicio
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return False, time.monotonic() - inicio


def parar(processo: subprocess.Popen | None) -> None:
    """Encerra o processo e seus filhos (no Windows o npm cria um processo filho do Node)."""
    if processo is None or processo.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"], capture_output=True)
    else:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()


def ambiente_da_api(env: dict[str, str]) -> dict[str, str]:
    filho = os.environ.copy()
    # O formulário só aceita a origem listada; localhost e 127.0.0.1 são endereços diferentes para o navegador.
    if not env.get("API_CORS_ORIGINS") and not filho.get("API_CORS_ORIGINS"):
        filho["API_CORS_ORIGINS"] = f"http://localhost:{PORTA_FRONT},http://127.0.0.1:{PORTA_FRONT}"
    return filho


def ambiente_do_front(env: dict[str, str]) -> dict[str, str]:
    filho = os.environ.copy()
    filho["API_URL"] = env.get("API_URL") or f"http://127.0.0.1:{PORTA_API}"
    if env.get("NEXT_PUBLIC_APEX_URL"):
        filho["NEXT_PUBLIC_APEX_URL"] = env["NEXT_PUBLIC_APEX_URL"]
    return filho


def compilar_front(env: dict[str, str]) -> bool:
    print("Compilando o front (leva cerca de um minuto)...")
    npm = shutil.which("npm") or "npm"
    return subprocess.run([npm, "run", "build"], cwd=WEB, env=ambiente_do_front(env)).returncode == 0


def executar(env: dict[str, str], abrir_navegador: bool, aquecer: bool = True) -> int:
    api = front = None
    try:
        print(f"Iniciando a API na porta {PORTA_API} (carrega os dados antes de responder)...")
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(PORTA_API)],
            cwd=RAIZ, env=ambiente_da_api(env),
        )
        if not esperar_url(f"http://127.0.0.1:{PORTA_API}/healthz", limite=300):
            print("A API não respondeu em 5 minutos. Veja as mensagens acima.")
            return 1
        print("API pronta.")

        if aquecer:
            print("Preparando a previsão (na primeira vez leva de 1 a 3 minutos; depois fica em memória)...")
            ok, segundos = aquecer_previsao(f"http://127.0.0.1:{PORTA_API}/api/previsao")
            if ok:
                print(f"Previsão pronta em {segundos:.0f}s.")
            else:
                print(f"Aviso: a previsão não ficou pronta ({segundos:.0f}s). A tela Previsões pode demorar na primeira abertura.")

        print(f"Iniciando o front na porta {PORTA_FRONT}...")
        npm = shutil.which("npm") or "npm"
        front = subprocess.Popen(
            [npm, "run", "start", "--", "--port", str(PORTA_FRONT)],
            cwd=WEB, env=ambiente_do_front(env),
        )
        if not esperar_url(URL_FRONT, limite=120):
            print("O front não respondeu em 2 minutos. Veja as mensagens acima.")
            return 1

        print(f"\nTudo no ar. Abra {URL_FRONT} (use localhost, não 127.0.0.1).")
        print("Para encerrar, pressione Ctrl+C.\n")
        if abrir_navegador:
            webbrowser.open(URL_FRONT)
        while True:
            time.sleep(2)
            for nome, processo in (("API", api), ("front", front)):
                if processo.poll() is not None:
                    print(f"\nO processo da {nome} terminou inesperadamente (código {processo.returncode}).")
                    return 1
    except KeyboardInterrupt:
        print("\nEncerrando...")
        return 0
    finally:
        parar(front)
        parar(api)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Modo apresentação do projeto Vigil.")
    ap.add_argument("--verificar", action="store_true", help="só verifica o ambiente")
    ap.add_argument("--build", action="store_true", help="refaz o build do front antes de iniciar")
    ap.add_argument("--sem-navegador", action="store_true", help="não abre o navegador")
    ap.add_argument("--sem-aquecer", action="store_true", help="não pré-calcula a previsão (a subida fica mais rápida)")
    args = ap.parse_args(argv)

    env = carregar_env()
    informativos = aplicar_env(env)
    itens = verificar_tudo(env)
    itens[1:1] = informativos  # logo depois do item do .env
    if not imprimir(itens):
        print("Corrija os itens [ERRO] e rode de novo.")
        return 1
    avisos = contar_avisos(itens)
    if args.verificar:
        if avisos:
            print(f"Pronto para os painéis, mas com {avisos} aviso(s) [ATENCAO] acima. "
                  "Resolva-os antes de demonstrar o Acolhimento.")
        else:
            print("Ambiente pronto para a demonstração.")
        return 0
    if avisos:
        print(f"Atenção: {avisos} aviso(s) acima. O Acolhimento pode não funcionar nesta execução.\n")

    if args.build or not build_existe():
        if not compilar_front(env):
            print("O build do front falhou. Veja as mensagens acima.")
            return 1
    return executar(env, abrir_navegador=not args.sem_navegador, aquecer=not args.sem_aquecer)


if __name__ == "__main__":
    sys.exit(main())
