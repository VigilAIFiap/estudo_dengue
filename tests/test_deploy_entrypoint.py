from __future__ import annotations

import base64
import importlib.util
import io
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("entrypoint", RAIZ / "deploy" / "entrypoint.py")
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)


def _zip_base64() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pacote:
        pacote.writestr("tnsnames.ora", "alias = (DESCRIPTION=...)")
        pacote.writestr("cwallet.sso", "conteudo")
    return base64.b64encode(buffer.getvalue()).decode()


class EntrypointTests(unittest.TestCase):
    def test_sem_variavel_nao_faz_nada(self):
        env: dict[str, str] = {}
        self.assertIsNone(entrypoint.preparar_wallet(env))
        self.assertEqual(env, {})

    def test_extrai_a_wallet_e_define_wallet_dir(self):
        with TemporaryDirectory() as pasta:
            env = {"WALLET_ZIP_B64": _zip_base64(), "WALLET_DIR": str(Path(pasta) / "w")}
            destino = entrypoint.preparar_wallet(env)
            self.assertEqual(destino, Path(pasta) / "w")
            self.assertTrue((destino / "tnsnames.ora").exists())
            self.assertTrue((destino / "cwallet.sso").exists())
            self.assertEqual(env["WALLET_DIR"], str(destino))

    def test_recusa_conteudo_que_nao_e_zip_em_base64(self):
        with self.assertRaisesRegex(SystemExit, "WALLET_ZIP_B64 inválida"):
            entrypoint.preparar_wallet({"WALLET_ZIP_B64": base64.b64encode(b"nao e zip").decode()})
        with self.assertRaisesRegex(SystemExit, "WALLET_ZIP_B64 inválida"):
            entrypoint.preparar_wallet({"WALLET_ZIP_B64": "###"})


if __name__ == "__main__":
    unittest.main()
