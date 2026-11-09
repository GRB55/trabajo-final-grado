-- Seguridad
-- Marcadores: (BASE, BI_PASSWORD, RUTA_AUDITORIA). Ejecutar con: python -m src.run_pipeline --paso seguridad
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_audits WHERE name = 'auditoria_ddjj')
  CREATE SERVER AUDIT auditoria_ddjj
  TO FILE (FILEPATH = N'__RUTA_AUDITORIA__', MAXSIZE = 100 MB, MAX_ROLLOVER_FILES = 50)
  WITH (ON_FAILURE = CONTINUE);
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_audit_specifications WHERE name = 'auditoria_ddjj_servidor')
  CREATE SERVER AUDIT SPECIFICATION auditoria_ddjj_servidor FOR SERVER AUDIT auditoria_ddjj
  ADD (FAILED_LOGIN_GROUP), ADD (SUCCESSFUL_LOGIN_GROUP),
  ADD (SERVER_ROLE_MEMBER_CHANGE_GROUP), ADD (SERVER_PERMISSION_CHANGE_GROUP)
  WITH (STATE = ON);
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'bi_reader')
  CREATE LOGIN bi_reader WITH PASSWORD = N'__BI_PASSWORD__', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
GO
USE [__BASE__];
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'bi_reader')
  CREATE USER bi_reader FOR LOGIN bi_reader;
GO
GRANT SELECT ON SCHEMA::oro TO bi_reader;
GRANT SELECT ON SCHEMA::resultados TO bi_reader;
DENY  SELECT ON SCHEMA::bronce TO bi_reader;
DENY  SELECT ON SCHEMA::plata TO bi_reader;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_audit_specifications WHERE name = 'auditoria_ddjj_base')
  CREATE DATABASE AUDIT SPECIFICATION auditoria_ddjj_base FOR SERVER AUDIT auditoria_ddjj
  ADD (DATABASE_PERMISSION_CHANGE_GROUP), ADD (DATABASE_ROLE_MEMBER_CHANGE_GROUP),
  ADD (SCHEMA_OBJECT_CHANGE_GROUP), ADD (SELECT ON SCHEMA::resultados BY public)
  WITH (STATE = ON);
GO
USE master;
GO
ALTER SERVER AUDIT auditoria_ddjj WITH (STATE = ON);
GO
