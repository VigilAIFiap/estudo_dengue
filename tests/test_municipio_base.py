from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from api.dataset import RAIZ_PROJETO, base_municipal_configurada, caminho_municipios, carregar  # noqa: E402

CABECALHO = "DT_NOTIFIC,NU_ANO,SG_UF_NOT,ID_MUNICIP,ID_MN_RESI,HOSPITALIZ,CLASSI_FIN,EVOLUCAO\n"
CABECALHO_SEM_RESIDENCIA = "DT_NOTIFIC,NU_ANO,SG_UF_NOT,ID_MUNICIP,HOSPITALIZ,CLASSI_FIN,EVOLUCAO\n"
MUNICIPIOS = (
    "codigo_ibge,nome,latitude,longitude,capital,codigo_uf,siafi_id,ddd,fuso_horario\n"
    "3550308,São Paulo,-23.5,-46.6,1,35,7107,11,America/Sao_Paulo\n"
    "1100205,Porto Velho,-8.7,-63.9,1,11,2,69,America/Porto_Velho\n"
    "5300108,Brasília,-15.8,-47.9,1,53,3,61,America/Sao_Paulo\n"
)


def _linhas(data: str, ano: str, notificacao: str, residencia: str, n: int) -> str:
    return "".join(f"{data},{ano},xx,{notificacao},{residencia},2,10,1\n" for _ in range(n))


def criar_base(pasta: Path, *, com_residencia: bool = True) -> None:
    cab = CABECALHO if com_residencia else CABECALHO_SEM_RESIDENCIA

    def linhas(data, ano, notificacao, residencia, n):
        texto = _linhas(data, ano, notificacao, residencia, n)
        if com_residencia:
            return texto
        # remove a coluna ID_MN_RESI de cada linha
        return "".join(",".join(p for i, p in enumerate(l.split(",")) if i != 4) for l in texto.splitlines(True))

    b25 = (
        cab
        + linhas("2025-01-06", "2025", "355030", "355030", 20)  # mora onde foi notificado
        + linhas("2025-01-07", "2025", "355030", "110020", 10)  # mora em Porto Velho, notificado em São Paulo
        + linhas("2025-02-03", "2025", "530010", "", 5)  # residência em branco
        + linhas("2025-02-04", "2025", "530010", "999999", 3)  # residência fora do cadastro
    )
    b26 = cab + linhas("2026-01-05", "2026", "355030", "530010", 2)
    (pasta / "DENGBR23.csv").write_text(cab, encoding="latin-1")
    (pasta / "DENGBR24.csv").write_text(cab, encoding="latin-1")
    (pasta / "DENGBR25.csv").write_text(b25, encoding="latin-1")
    (pasta / "DENGBR26.csv").write_text(b26, encoding="latin-1")
    (pasta / "municipios.csv").write_text(MUNICIPIOS, encoding="utf-8")


def contagem(ds) -> dict[int, int]:
    return {int(k): int(v) for k, v in ds.notificacoes["id_municip"].value_counts().items()}


class BaseMunicipalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.hoje = pd.Timestamp("2026-10-17")

    def tearDown(self):
        self.tmp.cleanup()

    def test_padrao_usa_o_municipio_de_notificacao(self):
        criar_base(self.pasta)
        with patch.dict("os.environ", {}, clear=False):
            ds = carregar(self.pasta, hoje=self.hoje)
        self.assertEqual(ds.base_municipal, "notificacao")
        self.assertEqual(ds.sem_residencia, 0)
        self.assertEqual(contagem(ds), {355030: 32, 530010: 8})

    def test_residencia_agrupa_pelo_municipio_do_paciente(self):
        criar_base(self.pasta)
        with patch.dict("os.environ", {"DENGUE_MUNICIPIO_BASE": "residencia"}):
            ds = carregar(self.pasta, hoje=self.hoje)
        self.assertEqual(ds.base_municipal, "residencia")
        # 20 em São Paulo, 10 em Porto Velho; 8 sem residência válida ficam em Brasília (notificação);
        # 2 notificadas em São Paulo moram em Brasília.
        self.assertEqual(contagem(ds), {355030: 20, 110020: 10, 530010: 10})
        self.assertEqual(ds.sem_residencia, 8)

    def test_uf_acompanha_o_municipio_de_residencia(self):
        criar_base(self.pasta)
        with patch.dict("os.environ", {"DENGUE_MUNICIPIO_BASE": "residencia"}):
            ds = carregar(self.pasta, hoje=self.hoje)
        ro = ds.notificacoes[ds.notificacoes["id_municip"] == 110020]
        self.assertEqual(set(ro["uf"].astype(str)), {"RO"})

    def test_residencia_exige_a_coluna_em_todos_os_arquivos(self):
        criar_base(self.pasta, com_residencia=False)
        with patch.dict("os.environ", {"DENGUE_MUNICIPIO_BASE": "residencia"}):
            with self.assertRaisesRegex(ValueError, "ID_MN_RESI"):
                carregar(self.pasta, hoje=self.hoje)

    def test_cadastro_de_municipios_cai_na_copia_versionada(self):
        with patch.dict("os.environ", {}, clear=False):
            os_env = __import__("os").environ
            os_env.pop("MUNICIPIOS_CSV", None)
            self.assertEqual(caminho_municipios(self.pasta), RAIZ_PROJETO / "api" / "data" / "municipios.csv")
            (self.pasta / "municipios.csv").write_text(MUNICIPIOS, encoding="utf-8")
            self.assertEqual(caminho_municipios(self.pasta), self.pasta / "municipios.csv")
        with patch.dict("os.environ", {"MUNICIPIOS_CSV": "/outro/caminho.csv"}):
            self.assertEqual(caminho_municipios(self.pasta), Path("/outro/caminho.csv"))

    def test_copia_versionada_do_cadastro_esta_completa(self):
        cadastro = pd.read_csv(RAIZ_PROJETO / "api" / "data" / "municipios.csv")
        self.assertEqual(len(cadastro), 5571)
        self.assertEqual(int(cadastro["codigo_ibge"].duplicated().sum()), 0)
        self.assertEqual(int(cadastro["nome"].isna().sum()), 0)

    def test_valor_invalido_da_variavel_e_recusado(self):
        with patch.dict("os.environ", {"DENGUE_MUNICIPIO_BASE": "moradia"}):
            with self.assertRaisesRegex(ValueError, "DENGUE_MUNICIPIO_BASE"):
                base_municipal_configurada()


if __name__ == "__main__":
    unittest.main()
