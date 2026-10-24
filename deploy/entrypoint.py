"""Prepara a wallet do Oracle (se vier em base64) e inicia a API.

A hospedagem entrega a wallet como variável de ambiente secreta WALLET_ZIP_B64 (o .zip da wallet em
base64). O conteúdo é extraído em WALLET_DIR (padrão /tmp/wallet) apenas dentro do contêiner.
"""

from __future__ import annotations

import base64
import binascii
import io
import os
import sys
import zipfile
from pathlib import Path


def preparar_wallet(env: dict[str, str] | None = None) -> Path | None:
    ambiente = os.environ if env is None else env
    conteudo = ambiente.get("WALLET_ZIP_B64", "").strip()
    if not conteudo:
        return None
    destino = Path(ambiente.get("WALLET_DIR") or "/tmp/wallet")
    try:
        pacote = zipfile.ZipFile(io.BytesIO(base64.b64decode(conteudo, validate=True)))
    except (binascii.Error, zipfile.BadZipFile) as erro:
        raise SystemExit(f"WALLET_ZIP_B64 inválida: precisa ser o .zip da wallet em base64 ({erro}).") from erro
    destino.mkdir(parents=True, exist_ok=True)
    with pacote:
        pacote.extractall(destino)
    ambiente["WALLET_DIR"] = str(destino)
    return destino


def main() -> None:
    preparar_wallet()
    porta = os.environ.get("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable, "-m", "uvicorn", "api.main:app",
            "--host", "0.0.0.0", "--port", porta,
            "--proxy-headers", "--forwarded-allow-ips", "*",
        ],
    )


if __name__ == "__main__":
    main()
