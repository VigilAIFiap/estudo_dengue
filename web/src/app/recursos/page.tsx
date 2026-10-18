import type { Metadata } from "next";
import { PageHeader } from "@/components/shell/page-header";
import { IntegrationNotice } from "@/components/ui/integration-notice";
import { Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/states";

export const metadata: Metadata = { title: "Recursos e custos" };

const FONTES = [
  { dado: "Custos de exames e procedimentos", fonte: "SIGTAP (tabela SUS)", campos: "Código do procedimento, valor unitário, competência" },
  { dado: "Consumo de insumos e equipamentos", fonte: "Secretarias municipais e estaduais", campos: "Município, mês, insumo, quantidade, unidade" },
  { dado: "Estoques", fonte: "Sistemas de almoxarifado das secretarias", campos: "Município, insumo, saldo, data de posição" },
  { dado: "Preços de aquisição", fonte: "ComprasNet / Portal da Transparência", campos: "Item, preço contratado, data, órgão comprador" },
];

const AREAS = [
  { titulo: "Consumo por município e mês", requer: "consumo de insumos" },
  { titulo: "Custos estimados", requer: "SIGTAP e preços de aquisição" },
  { titulo: "Comparação entre períodos", requer: "série histórica de consumo e custos" },
];

export default function RecursosPage() {
  return (
    <>
      <PageHeader
        titulo="Planejamento de recursos e custos"
        descricao="Consulta de insumos, estoques e custos por município e mês, cruzada com as notificações."
      />
      <IntegrationNotice titulo="Esta área depende de dados que o projeto ainda não tem">
        <p>
          A base atual contém só notificações SINAN. Não há consumo de insumos, estoques nem preços, então nenhum valor financeiro é exibido.
          A estrutura abaixo mostra o que será consultado assim que as fontes forem integradas à API.
        </p>
      </IntegrationNotice>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {AREAS.map((a) => (
          <Panel key={a.titulo} titulo={a.titulo} subtitulo="Aguardando integração">
            <EmptyState titulo="Sem dados integrados">Requer {a.requer}.</EmptyState>
          </Panel>
        ))}
      </div>

      <div className="mt-5">
        <Panel titulo="Fontes necessárias" subtitulo="Dados e campos mínimos para habilitar cada consulta">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-4 font-medium">Dado</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Fonte prevista</th>
                  <th scope="col" className="py-2 font-medium">Campos mínimos</th>
                </tr>
              </thead>
              <tbody>
                {FONTES.map((f) => (
                  <tr key={f.dado} className="border-t border-line">
                    <th scope="row" className="py-2 pr-4 text-left font-medium text-ink">{f.dado}</th>
                    <td className="py-2 pr-4 text-ink-2">{f.fonte}</td>
                    <td className="py-2 text-ink-2">{f.campos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  );
}
