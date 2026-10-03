# 🦟 Painel de Gestão de Recursos contra Dengue

Este projeto tem como objetivo fornecer um **painel integrado** para gestores de órgãos públicos, permitindo o acompanhamento, previsão e planejamento de recursos relacionados ao combate à dengue.  

---

## 📊 Estrutura do Projeto

### 1. Painel de Dados Históricos
- Casos por município e por estado  
- Criticidade por município e por estado  
- Mapas interativos:
  - Clima
  - Temperatura (mapa de calor)
  - Cruzamento entre temperatura e clima
  - Chuvas
- Relação de insumos consumidos  
- Estimativa de custos com equipamentos e insumos por município/mês  

### 2. Painel de Previsões (12 meses)
- Projeção de criticidade por município  
- Identificação de locais críticos  
- Planejamento de custos com exames e insumos  

### 3. Painel Assistente de Análise
- Interface para recepcionistas inserirem dados de pacientes  
- IA prevê:
  - Possibilidade de dengue  
  - Criticidade do caso (leve, moderado, grave)  
  - Indicação se é ou não dengue  

### 4. Vigil Assist (Chatbot)
- Chatbot disponível em tempo integral para auxiliar nas análises  
- Função extra: geração de relatórios comerciais com histórico de consultas do usuário  

---

## 🚀 Tecnologias Utilizadas

- **Frontend:** React ou Angular (painéis interativos)  
- **Backend:** Python (API, processamento de dados e integração com IA)  
  - Frameworks: FastAPI ou Flask  
  - Bibliotecas: Pandas, NumPy, scikit-learn, TensorFlow/PyTorch  
- **Banco de Dados:** Oracle Database  
  - Conexão via `cx_Oracle`  
  - Procedures e triggers para cálculos de custos e criticidade  
- **Visualização:** Power BI, Grafana ou D3.js  

---

## 🗄️ Estrutura de Banco de Dados (Oracle)

### Tabelas principais:
- **CasosHistoricos** → registros de casos por município/estado  
- **Previsoes** → projeções de criticidade e custos  
- **Insumos** → controle de equipamentos e insumos consumidos  
- **Pacientes** → dados básicos e resultados da análise da IA  
- **ConsultasUsuario** → histórico de interações para relatórios do Vigil Assist  

---

## 🎯 Objetivos

- Apoiar gestores públicos na tomada de decisão  
- Antecipar cenários críticos de dengue  
- Otimizar o uso de recursos e insumos  
- Melhorar o atendimento ao paciente com suporte de IA  

---

## 📌 Próximos Passos

1. Definição da arquitetura do sistema  
2. Criação dos dashboards iniciais com dados históricos  
3. Implementação dos modelos de previsão em Python  
4. Desenvolvimento do chatbot Vigil Assist  
5. Testes e validação com dados reais  

---

## 📚 Referências de Dados

Para alimentar os painéis e modelos de previsão, serão utilizadas as seguintes fontes oficiais:

### 🦟 Epidemiológicos
- **SINAN/DATASUS** → Casos confirmados, suspeitos e óbitos de dengue  
  - [DATASUS](http://www2.datasus.gov.br/DATASUS/index.php)  
- **Secretarias Estaduais e Municipais de Saúde** → Boletins epidemiológicos semanais  
- **Ministério da Saúde – SAGE** → Indicadores estratégicos de saúde  

### 🌦️ Climáticos e Ambientais
- **INMET (Instituto Nacional de Meteorologia)** → Temperatura, chuva, umidade  
  - [INMET](https://portal.inmet.gov.br/)  
- **CPTEC/INPE** → Mapas de previsão e satélite  
  - [CPTEC/INPE](https://www.cptec.inpe.br/)  
- **ANA (Agência Nacional de Águas)** → Dados pluviométricos e hidrológicos  
  - [ANA](https://www.gov.br/ana/pt-br)  
- **NOAA / WorldClim** → Bases globais de clima e temperatura  

### 🏥 Saúde Pública
- **CNES (Cadastro Nacional de Estabelecimentos de Saúde)** → Leitos, equipamentos e profissionais  
  - [CNES](http://cnes.datasus.gov.br/)  
- **Secretarias Estaduais de Saúde** → Relatórios de exames e atendimentos  
- **Hospitais Regionais e UBS** → Dados internos de atendimento  

### 📦 Recursos e Custos
- **SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos do SUS)** → Custos de exames e procedimentos  
  - [SIGTAP](http://sigtap.datasus.gov.br/)  
- **ComprasNet / Portal da Transparência** → Contratos e aquisições públicas  
  - [ComprasNet](https://www.gov.br/compras/pt-br)  
  - [Portal da Transparência](http://www.portaltransparencia.gov.br/)  

### 👥 Pacientes
- **Hospitais e UBS locais** → Dados clínicos e laboratoriais  
- **Lacen (Laboratórios Centrais de Saúde Pública)** → Resultados de exames confirmatórios  
- **SINAN** → Notificações individuais com sintomas e evolução  

### 🤖 IA e Previsões
- **Bases históricas de surtos (SINAN + INMET)** → Para cruzamento de clima e incidência  
- **Literatura científica (SciELO, PubMed)** → Estudos sobre correlação clima/dengue  

---

📌 **Observação:**  
Os dados do **SINAN 2025 e 2026** já foram coletados e servirão como base inicial para os painéis históricos e de previsão.


👨‍💻 **Equipe:** Projeto em desenvolvimento colaborativo  
📅 **Status:** Planejamento inicial  
