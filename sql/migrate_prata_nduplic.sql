-- Execute no schema Oracle que ja possui a tabela PRATA.
-- Mantem compatibilidade com cargas que ainda nao possuem NDUPLIC_N.
DECLARE
    column_count PLS_INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO column_count
    FROM USER_TAB_COLUMNS
    WHERE TABLE_NAME = 'PRATA'
      AND COLUMN_NAME = 'NDUPLIC_N';

    IF column_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE PRATA ADD (NDUPLIC_N NUMBER(2))';
    END IF;
END;
/
