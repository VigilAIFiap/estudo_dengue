from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo", RAIZ / "scripts" / "demo.py")
demo = importlib.util.module_from_spec(spec)
sys.modules["demo"] = demo  # necessário para o @dataclass do módulo
spec.loader.exec_module(demo)

CABECALHO = "DT_NOTIFIC,NU_ANO,SG_UF_NOT,ID_MUNICIP,HOSPITALIZ,CLASSI_FIN,EVOLUCAO\n"


def criar_dados(pasta: Path, cabecalho: str = CABECALHO) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in demo.ARQUIVOS_ANUAIS:
        (pasta / nome).write_text(cabecalho, encoding="latin-1")


class Saude(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_):
        pass


class ConfiguracaoTests(unittest.TestCase):
    def test_carregar_env_le_o_arquivo_e_ignora_comentarios(self):
        with TemporaryDirectory() as pasta:
            (Path(pasta) / ".env").write_text("# comentario\nDATA_SOURCE=csv\nTRIAGE_FORM_ENABLED='true'\n", encoding="utf-8")
            env = demo.carregar_env(Path(pasta))
        self.assertEqual(env, {"DATA_SOURCE": "csv", "TRIAGE_FORM_ENABLED": "true"})

    def test_carregar_env_sem_arquivo_devolve_vazio(self):
        with TemporaryDirectory() as pasta:
            self.assertEqual(demo.carregar_env(Path(pasta)), {})

    def test_verdadeiro(self):
        self.assertTrue(all(demo.verdadeiro(v) for v in ("true", "TRUE", "1", "sim", " on ")))
        self.assertFalse(any(demo.verdadeiro(v) for v in ("false", "", None, "0")))

    def test_versao_do_node(self):
        self.assertEqual(demo.versao_node("v22.1.0\n"), (22, 1))
        self.assertGreaterEqual(demo.versao_node("v20.9.0"), (20, 9))
        self.assertEqual(demo.versao_node("lixo"), (0, 0))


class VerificacoesTests(unittest.TestCase):
    def test_sem_env_a_verificacao_para_com_erro_critico(self):
        with TemporaryDirectory() as pasta:
            itens = demo.verificar_tudo({}, com_oracle=False, raiz=Path(pasta))
        self.assertEqual(len(itens), 1)
        self.assertFalse(itens[0].ok)
        self.assertTrue(itens[0].critico)

    def test_formulario_desligado_e_apenas_um_aviso(self):
        with TemporaryDirectory() as pasta:
            (Path(pasta) / ".env").write_text("", encoding="utf-8")
            itens = demo.verificar_env({"TRIAGE_FORM_ENABLED": "false"}, Path(pasta))
        formulario = [i for i in itens if i.nome == "Formulário de acolhimento"][0]
        self.assertFalse(formulario.ok)
        self.assertFalse(formulario.critico)

    def test_formulario_ligado(self):
        with TemporaryDirectory() as pasta:
            (Path(pasta) / ".env").write_text("", encoding="utf-8")
            itens = demo.verificar_env({"TRIAGE_FORM_ENABLED": "true"}, Path(pasta))
        self.assertTrue([i for i in itens if i.nome == "Formulário de acolhimento"][0].ok)

    def test_arquivos_do_sinan_faltando_sao_listados(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            criar_dados(raiz / "dados" / "raw")
            (raiz / "dados" / "raw" / "DENGBR24.csv").unlink()
            itens = demo.verificar_dados_csv({}, raiz)
        self.assertFalse(itens[0].ok)
        self.assertIn("DENGBR24.csv", itens[0].detalhe)

    def test_arquivos_completos_passam(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            criar_dados(raiz / "dados" / "raw")
            itens = demo.verificar_dados_csv({}, raiz)
        self.assertTrue(all(i.ok for i in itens))

    def test_modo_oracle_nao_exige_csvs(self):
        with TemporaryDirectory() as pasta:
            self.assertEqual(demo.verificar_dados_csv({"DATA_SOURCE": "oracle"}, Path(pasta)), [])

    def test_residencia_exige_a_coluna_em_todos_os_arquivos(self):
        env = {"DENGUE_MUNICIPIO_BASE": "residencia"}
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            criar_dados(raiz / "dados" / "raw")
            itens = demo.verificar_dados_csv(env, raiz)
            self.assertFalse(itens[-1].ok)
            criar_dados(raiz / "dados" / "raw", CABECALHO.replace("ID_MUNICIP", "ID_MUNICIP,ID_MN_RESI"))
            itens = demo.verificar_dados_csv(env, raiz)
            self.assertTrue(itens[-1].ok)

    def test_detecta_valor_repetido_no_env(self):
        itens = demo.verificar_valores_repetidos({"DB_DSN": "DB_DSN=adwsus_low", "DB_USER": "VIGIL_APEX"})
        self.assertEqual(len(itens), 1)
        self.assertIn("DB_DSN", itens[0].detalhe)
        self.assertFalse(itens[0].critico)  # fonte CSV: o Acolhimento não grava, mas os painéis funcionam
        self.assertTrue(demo.verificar_valores_repetidos({"DATA_SOURCE": "oracle", "DB_DSN": "DB_DSN=x"})[0].critico)
        self.assertEqual(demo.verificar_valores_repetidos({"DB_DSN": "adwsus_low"}), [])

    def test_env_vale_mesmo_quando_a_sessao_define_outro_valor(self):
        env = {"TRIAGE_FORM_ENABLED": "true", "DB_USER": "VIGIL_APEX", "DB_PASSWORD": "senha-do-env"}
        sessao = {"TRIAGE_FORM_ENABLED": "false", "DB_USER": "ADMIN", "DB_PASSWORD": "senha-do-admin", "PATH": "x"}
        itens = demo.aplicar_env(env, sessao)
        # o ambiente passa a ter os valores do .env (é o que a API e o front herdam)
        self.assertEqual(sessao["TRIAGE_FORM_ENABLED"], "true")
        self.assertEqual(sessao["DB_USER"], "VIGIL_APEX")
        self.assertEqual(sessao["DB_PASSWORD"], "senha-do-env")
        self.assertEqual(sessao["PATH"], "x")
        # a API só aceita exatamente "true": confere a mesma regra do endpoint
        self.assertEqual(sessao["TRIAGE_FORM_ENABLED"].strip().lower(), "true")
        # aviso informativo, sem exibir segredos
        self.assertEqual(len(itens), 1)
        self.assertTrue(itens[0].ok)
        detalhe = itens[0].detalhe
        self.assertIn('TRIAGE_FORM_ENABLED (sessão: "false"; .env: "true")', detalhe)
        self.assertIn('DB_USER (sessão: "ADMIN"; .env: "VIGIL_APEX")', detalhe)
        self.assertIn("DB_PASSWORD (valor diferente do .env)", detalhe)
        self.assertNotIn("senha-do-admin", detalhe)
        self.assertNotIn("senha-do-env", detalhe)

    def test_sem_conflito_nao_ha_aviso_e_o_env_e_aplicado(self):
        sessao = {"DB_DSN": "adwsus_low"}
        self.assertEqual(demo.aplicar_env({"DB_DSN": "adwsus_low", "DATA_SOURCE": "csv"}, sessao), [])
        self.assertEqual(sessao["DATA_SOURCE"], "csv")  # chave nova também é aplicada
        self.assertEqual(demo.aplicar_env({}, {}), [])

    def test_avalia_a_conexao_com_o_oracle(self):
        ok, detalhe = demo.avaliar_conexao("VIGIL_APEX", "VIGIL_APEX", 5)
        self.assertTrue(ok)
        ok, detalhe = demo.avaliar_conexao("ADMIN", "ADMIN", 0)
        self.assertFalse(ok)
        self.assertIn("conectado como ADMIN (schema ADMIN)", detalhe)
        self.assertIn("sessão do PowerShell", detalhe)
        ok, detalhe = demo.avaliar_conexao("VIGIL_APEX", "ADMIN", 5)  # schema trocado por ALTER SESSION
        self.assertFalse(ok)
        ok, detalhe = demo.avaliar_conexao("VIGIL_APEX", "VIGIL_APEX", 3)
        self.assertFalse(ok)
        self.assertIn("só 3", detalhe)

    def test_conta_apenas_avisos_nao_criticos(self):
        itens = [
            demo.Item("a", True, "ok"),
            demo.Item("b", False, "aviso", critico=False),
            demo.Item("c", False, "erro", critico=True),
        ]
        self.assertEqual(demo.contar_avisos(itens), 1)

    def test_imprimir_so_reprova_item_critico(self):
        aviso = demo.Item("a", False, "x", critico=False)
        erro = demo.Item("b", False, "y", critico=True)
        certo = demo.Item("c", True, "z")
        with patch("builtins.print"):
            self.assertTrue(demo.imprimir([certo, aviso]))
            self.assertFalse(demo.imprimir([certo, aviso, erro]))


class RedeTests(unittest.TestCase):
    def test_porta_em_uso(self):
        servidor = socket.socket()
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        porta = servidor.getsockname()[1]
        try:
            self.assertTrue(demo.porta_em_uso(porta))
        finally:
            servidor.close()
        self.assertFalse(demo.porta_em_uso(porta))

    def test_esperar_url_responde_quando_o_servico_esta_no_ar(self):
        servidor = HTTPServer(("127.0.0.1", 0), Saude)
        fio = threading.Thread(target=servidor.serve_forever, daemon=True)
        fio.start()
        try:
            self.assertTrue(demo.esperar_url(f"http://127.0.0.1:{servidor.server_port}/healthz", limite=5, intervalo=0.1))
        finally:
            servidor.shutdown()
            servidor.server_close()

    def test_aquecer_previsao_mede_o_tempo_quando_a_api_responde(self):
        servidor = HTTPServer(("127.0.0.1", 0), Saude)
        fio = threading.Thread(target=servidor.serve_forever, daemon=True)
        fio.start()
        try:
            ok, segundos = demo.aquecer_previsao(f"http://127.0.0.1:{servidor.server_port}/api/previsao", limite=5)
        finally:
            servidor.shutdown()
            servidor.server_close()
        self.assertTrue(ok)
        self.assertGreaterEqual(segundos, 0)

    def test_aquecer_previsao_nao_levanta_erro_quando_a_api_esta_fora(self):
        livre = socket.socket()
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]
        livre.close()
        ok, segundos = demo.aquecer_previsao(f"http://127.0.0.1:{porta}/api/previsao", limite=2)
        self.assertFalse(ok)

    def test_esperar_url_desiste_depois_do_limite(self):
        livre = socket.socket()
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]
        livre.close()
        self.assertFalse(demo.esperar_url(f"http://127.0.0.1:{porta}/", limite=0.6, intervalo=0.2))


class AmbienteTests(unittest.TestCase):
    def test_api_aceita_localhost_e_127_por_padrao(self):
        with patch.dict("os.environ", {}, clear=True):
            filho = demo.ambiente_da_api({})
        self.assertEqual(filho["API_CORS_ORIGINS"], "http://localhost:3000,http://127.0.0.1:3000")

    def test_api_respeita_a_origem_configurada(self):
        with patch.dict("os.environ", {}, clear=True):
            filho = demo.ambiente_da_api({"API_CORS_ORIGINS": "http://meu.site"})
        self.assertNotIn("API_CORS_ORIGINS", filho)  # o .env da API será lido por ela mesma

    def test_front_recebe_api_url_e_link_do_apex(self):
        with patch.dict("os.environ", {}, clear=True):
            filho = demo.ambiente_do_front({"NEXT_PUBLIC_APEX_URL": "https://apex.exemplo/app"})
        self.assertEqual(filho["API_URL"], "http://127.0.0.1:8000")
        self.assertEqual(filho["NEXT_PUBLIC_APEX_URL"], "https://apex.exemplo/app")


if __name__ == "__main__":
    unittest.main()
