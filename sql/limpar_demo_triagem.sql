-- Limpa os dados de demonstração da triagem: APAGA TODOS os registros das três tabelas.
--
-- Use antes de uma apresentação para começar com a fila vazia, ou depois dela. É destrutivo e irreversível:
-- só execute se todos os registros dessas tabelas forem fictícios (MVP de demonstração).
-- Execute CONECTADO COMO VIGIL_APEX. Tudo acontece em um único bloco: se o schema ativo não for o
-- VIGIL_APEX, nada é apagado.

SET SERVEROUTPUT ON

DECLARE
    V_SCHEMA VARCHAR2(128) := SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA');
    V_LOG NUMBER;
    V_APROVADO NUMBER;
    V_FILA NUMBER;
BEGIN
    IF V_SCHEMA <> 'VIGIL_APEX' THEN
        RAISE_APPLICATION_ERROR(-20900, 'Schema ativo: ' || V_SCHEMA || '. Conecte como VIGIL_APEX. Nada foi apagado.');
    END IF;

    -- Ordem imposta pelas chaves estrangeiras: histórico e aprovados antes da fila.
    DELETE FROM VIGIL_TRIAGE_REVIEW_LOG;
    V_LOG := SQL%ROWCOUNT;
    DELETE FROM VIGIL_TRIAGE_APROVADO;
    V_APROVADO := SQL%ROWCOUNT;
    DELETE FROM VIGIL_TRIAGE_INTAKE;
    V_FILA := SQL%ROWCOUNT;
    COMMIT;

    DBMS_OUTPUT.PUT_LINE('Apagados: ' || V_LOG || ' do histórico, ' || V_APROVADO || ' aprovados e ' || V_FILA || ' da fila.');
END;
/
