-- Prepara dados FICTÍCIOS para a demonstração da triagem no Oracle APEX.
--
-- Execute CONECTADO COMO VIGIL_APEX, depois de sql/migrate_triage_approval.sql.
-- Cria 4 registros de exemplo: 2 completos e consistentes (o gatilho os aprova na hora, com revisor AUTO)
-- e 2 com problema (ficam PENDENTE na fila do APEX para você aprovar ou rejeitar ao vivo).
-- Serve de plano B caso o formulário do front não funcione durante a apresentação.
-- O bloco aborta se o schema ativo não for VIGIL_APEX.

SET SERVEROUTPUT ON

DECLARE
    V_SCHEMA VARCHAR2(128) := SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA');

    PROCEDURE NOVO(
        P_AGE IN VARCHAR2, P_SEX IN VARCHAR2, P_DURATION IN VARCHAR2,
        P_FEVER IN VARCHAR2, P_HEADACHE IN VARCHAR2, P_MUSCLE IN VARCHAR2,
        P_RASH IN VARCHAR2, P_NAUSEA IN VARCHAR2, P_VOMITING IN VARCHAR2,
        P_PREGNANCY IN VARCHAR2, P_COMORB IN VARCHAR2
    ) IS
    BEGIN
        INSERT INTO VIGIL_TRIAGE_INTAKE (
            AGE_GROUP, SEX, SYMPTOM_DURATION, FEVER, HEADACHE, MUSCLE_PAIN,
            RASH, NAUSEA, VOMITING, PREGNANCY, COMORBIDITIES
        ) VALUES (
            P_AGE, P_SEX, P_DURATION, P_FEVER, P_HEADACHE, P_MUSCLE,
            P_RASH, P_NAUSEA, P_VOMITING, P_PREGNANCY, P_COMORB
        );
    END NOVO;
BEGIN
    IF V_SCHEMA <> 'VIGIL_APEX' THEN
        RAISE_APPLICATION_ERROR(-20900, 'Schema ativo: ' || V_SCHEMA || '. Conecte como VIGIL_APEX.');
    END IF;

    -- 1. Completo e consistente: aprovado automaticamente
    NOVO('20-39', 'F', '1-3_DIAS', 'SIM', 'SIM', 'SIM', 'NAO', 'NAO', 'NAO', 'NAO', 'NAO');
    -- 2. Completo; gestação não se aplica ao sexo masculino: aprovado automaticamente
    NOVO('40-59', 'M', 'HOJE', 'SIM', 'NAO', 'SIM', 'NAO', 'SIM', 'NAO', NULL, 'SIM');
    -- 3. Incompleto (febre não informada): fica PENDENTE
    NOVO('10-19', 'F', '4+_DIAS', NULL, 'SIM', 'NAO', 'NAO', 'NAO', 'NAO', 'NAO', 'NAO');
    -- 4. Inconsistente (sexo masculino com gestação): fica PENDENTE
    NOVO('20-39', 'M', '1-3_DIAS', 'SIM', 'SIM', 'SIM', 'NAO', 'NAO', 'NAO', 'SIM', 'NAO');

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Registros de demonstração criados. Esperado: 2 APROVADO e 2 PENDENTE.');
END;
/

SELECT STATUS, COUNT(*) AS REGISTROS FROM VIGIL_TRIAGE_INTAKE GROUP BY STATUS ORDER BY STATUS;
SELECT INTAKE_ID, STATUS, CAMPOS_FALTANTES, INCONSISTENCIAS, PODE_APROVAR FROM VIGIL_TRIAGE_REVIEW_QUEUE;
