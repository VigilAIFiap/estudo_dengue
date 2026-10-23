# Roteiro de demonstração (stand)

Este roteiro assume o projeto rodando **no próprio notebook**, com o `scripts/demo.py`. Os painéis funcionam sem
internet. O Acolhimento e o Oracle APEX precisam do Oracle na nuvem, então leve uma segunda rede (compartilhamento do
celular).

## A mensagem central

Diga isto em três frases, e volte a elas no fim:

1. **O problema:** os gestores de saúde têm dados de dengue, mas não têm uma leitura rápida de onde a situação é
   mais grave e para onde olhar primeiro.
2. **A solução:** um painel que mostra a situação do período, localiza os municípios críticos no mapa, projeta os
   próximos meses e explica cada cálculo.
3. **O diferencial:** na triagem, os dados são validados **no banco Oracle**. O que está correto entra
   automaticamente; o que tem erro **não sobe** e vai para a revisão de um analista no Oracle APEX, com histórico.

---

## 1. Preparação

### Um dia antes
- [ ] Rode `python scripts\demo.py --verificar` e corrija tudo que aparecer como `[ERRO]`.
- [ ] Rode `python scripts\demo.py --build` uma vez para ter o front compilado com o código mais recente.
- [ ] No `.env`: `TRIAGE_FORM_ENABLED=true` e, se quiser o link para o APEX na tela, `NEXT_PUBLIC_APEX_URL` (refaça o
      build depois de mudar).
- [ ] Teste o Oracle e o APEX com a internet do celular, e não só com a do seu local de trabalho.
- [ ] Execute `sql/limpar_demo_triagem.sql` (fila vazia) e depois `sql/preparar_demo_triagem.sql` (dados fictícios de reserva).
- [ ] Faça um ensaio completo, cronometrado, no notebook que será usado.
- [ ] **Grave um vídeo da demonstração completa** (tecla `Win + G` no Windows) e tire capturas de tela (`Win + Shift + S`).
      É o plano B.
- [ ] Carregue o notebook e o celular e leve os carregadores.

### 30 minutos antes
- [ ] Notebook na tomada, modo "Alto desempenho", suspensão desligada, notificações silenciadas.
- [ ] Feche tudo que não for a demonstração. Aumente o zoom do navegador (`Ctrl +`) até a leitura ficar confortável à distância.
- [ ] Conecte à rede e rode `python scripts\demo.py`. Espere a mensagem "Tudo no ar".
- [ ] Deixe abertas, em abas já logadas: **1)** `http://localhost:3000` **2)** o aplicativo do Oracle APEX, na página TRIAGEM.
- [ ] Use sempre `localhost`, nunca `127.0.0.1`: o formulário só aceita a origem `localhost`.
- [ ] Anote, **na hora**, os números que vai citar (notificações, município mais crítico, período). Não decore números de
      ensaios antigos: eles mudam com os filtros e com a base.

---

## 2. Roteiro de 5 minutos

| Tempo | Tela | O que mostrar | O que dizer |
| --- | --- | --- | --- |
| 0:00 | Visão geral | Apenas abra a tela. | A mensagem central, em 20 segundos. |
| 0:30 | Visão geral | O destaque "Resultado do período" e a faixa de **fonte e período** no topo. | "Toda tela mostra a fonte, o SINAN do DATASUS, e o período analisado. O destaque já diz onde olhar primeiro." |
| 1:00 | Visão geral | Indicadores coloridos e as **variações** em vermelho (aumento) ou verde (queda). | "Cada indicador compara com o mesmo período do ano anterior. Vermelho é piora, verde é melhora." |
| 1:30 | Mapa | Camada **Criticidade**; clique em um município crítico. | "Cada município recebe um nível. As áreas em branco sugerem um estado silencioso, onde as notificações ainda estão em atraso." |
| 2:15 | Municípios | Role até a **metodologia do score**. | "O score é volume multiplicado por severidade. Eu revisei esse cálculo: no desenho anterior, quase todo o ranking dependia só do volume. Agora a gravidade pesa de verdade." |
| 3:00 | Previsões | O gráfico e a seção de **metodologia**. | "Modelo SARIMA mensal, 12 meses à frente, validado contra um baseline simples. Se o modelo não superar o baseline, a tela diz." |
| 3:30 | Acolhimento | O fluxo de 3 etapas e o **Caso A** (aprovado na hora). | Ver a seção 3. |
| 4:15 | Acolhimento e APEX | O **Caso B** e a fila no APEX. | Ver a seção 3. |
| 4:45 | Fecho | Volte à Visão geral. | A mensagem central. "Dado errado não sobe: o banco decide, e um analista revisa o que sobra." |

### Versão de 90 segundos
Visão geral (resultado do período) → Mapa (um município crítico) → Acolhimento (Caso A e Caso B, só a prévia e o resultado).

### Versão de 10 minutos
Acrescente: a Análise histórica (série por semana, com a régua para aproximar), a comparação de municípios, o
detalhe de um município (a decomposição do score) e a revisão das pendências no APEX.

---

## 3. O Acolhimento e o APEX (o ponto alto)

**Antes de começar:** diga que o formulário **não coleta nome, documento nem texto livre**, e que a demonstração usa
dados fictícios. A tela já traz esse aviso.

### Caso A: registro correto, aprovado automaticamente
1. Faixa etária **20 a 39**, sexo **Feminino**, início **Há 1 a 3 dias**.
2. Febre **Sim**, dor de cabeça **Sim**, dor muscular **Sim**, manchas **Não**, náusea **Não**, vômito **Não**.
3. Gestação **Não**, comorbidades **Não**.
4. Mostre a **prévia** ao lado mudando enquanto você preenche, até "Pronto para aprovação automática".
5. Clique em **Enviar triagem** e leia o resultado: **"Aprovado automaticamente"**.
6. Fala: "As regras rodaram no banco, no instante do envio. Como estava correto, o registro entrou na base aprovada sem
   intervenção."

### Caso B: registro com erro, vai para revisão
1. Faixa etária **20 a 39**, sexo **Masculino**, início **Há 1 a 3 dias**, **febre não informada**.
2. Demais sintomas à escolha e **Gestação: Sim**.
3. A prévia mostra "Irá para revisão no APEX", com os campos que faltam e a inconsistência.
4. Envie. O resultado diz **"Enviado para revisão no APEX"** e lista o motivo.
5. Fala: "O formulário não bloqueia o envio, mas o dado com erro não sobe. Quem decide é o banco."

### No Oracle APEX (página TRIAGEM)
1. Atualize a página: o protocolo do Caso B aparece na fila, com campos faltantes e inconsistências.
2. Escolha o protocolo e clique em **Aprovar**: o banco **recusa**, com a mensagem do motivo. Fala: "Mesmo um analista
   não consegue aprovar um registro inválido."
3. Digite uma nota e clique em **Rejeitar**: o registro sai da fila.
4. Fecha: "Cada decisão fica gravada no histórico, com quem fez e quando."

Se quiser mostrar o resultado no banco, rode no SQL Workshop:
```sql
SELECT STATUS, COUNT(*) FROM VIGIL_TRIAGE_INTAKE GROUP BY STATUS;
SELECT * FROM VIGIL_TRIAGE_REVIEW_LOG ORDER BY LOG_ID DESC;
```

---

## 4. Perguntas prováveis

| Pergunta | Resposta |
| --- | --- |
| De onde vêm os dados? | Das notificações de dengue do SINAN, do DATASUS. Cada tela mostra a fonte e o período. |
| O sistema diagnostica? | Não. É apoio à gestão e à triagem; não diagnostica nem define prioridade de atendimento. |
| E a privacidade? | O formulário só recebe faixa etária, sexo e respostas sim/não. Não há nome, documento nem texto livre. |
| O que é o "em branco" no mapa? | Municípios sem notificação no período. A base usa o município de notificação ou, quando configurado, o de residência. O texto da legenda explica. |
| Como o score é calculado? | Volume (log das notificações) multiplicado pela severidade (percentis das taxas de óbito e hospitalização, suavizadas). A fórmula está na tela de Municípios. |
| Por que o score mudou? | Na revisão, vi que o ranking dependia quase só do volume e que um município com poucos casos aparecia acima de grandes cidades. A fórmula nova corrige isso. |
| Por que SARIMA? | Os casos de dengue têm sazonalidade anual forte e a série é curta. O SARIMA lida com isso e é comparado a um baseline simples. |
| A previsão é confiável? | Ela é validada em 9 meses de teste e comparada a um baseline. É uma projeção, não uma garantia, e a tela mostra o intervalo de 95%. |
| O que o Oracle faz? | Guarda os dados e aplica as regras de validação, aprova automaticamente o que está correto e mantém a fila e o histórico de revisão no APEX. |
| E se o profissional errar um campo? | O dado inconsistente não é aprovado: vai para a fila, e o analista o rejeita ou o trata. |
| Dá para usar em produção? | É um MVP. Antes disso, faltam autenticação, perfis de acesso e uma avaliação formal com especialistas de saúde. |

---

## 5. Plano B

| Se acontecer | Faça |
| --- | --- |
| Sem internet | Os painéis continuam funcionando. Troque para a rede do celular. Se não voltar, mostre o Acolhimento pelo vídeo gravado. |
| Formulário dá erro ao enviar | Mostre o erro como parte do fluxo ("o banco recusou") e passe ao APEX, onde os dados de `preparar_demo_triagem.sql` já estão na fila. |
| Oracle ou APEX fora do ar | Use o vídeo e as capturas de tela do Acolhimento e do APEX. |
| API caiu (tela sem dados) | Em outro terminal, rode `python scripts\demo.py` de novo. Enquanto isso, use as capturas. |
| Front travou | Atualize a página (`F5`). Se persistir, reinicie o `demo.py`. |
| Tela muito pequena para o público | `Ctrl +` no navegador, e use a tela cheia (`F11`). |
| Esqueceu um número | Diga "na tela está o valor do período" e aponte. Nunca arrisque um número de cabeça. |

---

## 6. Ao encerrar

- Pare tudo com `Ctrl + C` no terminal do `demo.py`.
- Se quiser a fila limpa, rode `sql/limpar_demo_triagem.sql`.
- Não deixe a wallet, o `.env` nem as senhas em nenhum computador emprestado.

## Cola de uma página

```
ANTES      python scripts\demo.py --verificar    |  .env: TRIAGE_FORM_ENABLED=true
LIGAR      python scripts\demo.py                |  http://localhost:3000 (nunca 127.0.0.1)
ORDEM      Visão geral > Mapa > Municípios (score) > Previsões > Acolhimento > APEX
CASO A     20 a 39 | Feminino | 1-3 dias | febre S, cefaleia S, dor muscular S, resto N | gestação N, comorb. N  -> aprova sozinho
CASO B     20 a 39 | Masculino | 1-3 dias | febre em branco | gestação SIM                -> vai para revisão no APEX
APEX       Aprovar = recusado pelo banco  |  Rejeitar com nota = sai da fila e grava histórico
PLANO B    vídeo + capturas  |  preparar_demo_triagem.sql
FECHAR     Ctrl+C  |  limpar_demo_triagem.sql
```
