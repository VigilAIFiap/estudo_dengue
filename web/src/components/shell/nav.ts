import {
  LayoutDashboard,
  LineChart,
  ListOrdered,
  Map,
  Package,
  Stethoscope,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export type ItemNav = { href: string; rotulo: string; icone: LucideIcon; descricao: string };

export const NAV_ANALISE: ItemNav[] = [
  { href: "/", rotulo: "Visão geral", icone: LayoutDashboard, descricao: "Situação epidemiológica do período" },
  { href: "/historico", rotulo: "Análise histórica", icone: LineChart, descricao: "Séries e comparação entre anos" },
  { href: "/mapa", rotulo: "Mapa", icone: Map, descricao: "Distribuição geográfica e criticidade" },
  { href: "/municipios", rotulo: "Municípios", icone: ListOrdered, descricao: "Ranking, detalhe e comparação" },
  { href: "/previsoes", rotulo: "Previsões", icone: TrendingUp, descricao: "Modelo SARIMA mensal" },
];

export const NAV_OPERACAO: ItemNav[] = [
  { href: "/recursos", rotulo: "Recursos e custos", icone: Package, descricao: "Insumos, estoques e custos" },
  { href: "/pacientes", rotulo: "Acolhimento", icone: Stethoscope, descricao: "Formulário para avaliação no APEX" },
];

export const TODOS = [...NAV_ANALISE, ...NAV_OPERACAO];
