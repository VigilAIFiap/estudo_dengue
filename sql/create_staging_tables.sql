-- Execute uma vez no schema Oracle que contém PRATA e OURO.
-- As tabelas de staging copiam a estrutura sem constraints/índices.
-- O carregador pode limpar somente estas tabelas e nunca altera produção.

CREATE TABLE PRATA_STG AS
SELECT *
FROM PRATA
WHERE 1 = 0;

CREATE TABLE OURO_STG AS
SELECT *
FROM OURO
WHERE 1 = 0;
