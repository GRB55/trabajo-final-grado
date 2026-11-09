-- Respaldo: configuración (una sola vez) y comandos manuales.
-- Los respaldos periódicos los ejecuta src/respaldo.py (completo semanal, diferencial diario).
-- Marcadores: CLAVE_MASTER, CLAVE_CERTIFICADO, RUTA_RESPALDO

-- 1) UNA SOLA VEZ: certificado para cifrar los respaldos (AES-256)
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
  CREATE MASTER KEY ENCRYPTION BY PASSWORD = N'__CLAVE_MASTER__';
GO
IF NOT EXISTS (SELECT 1 FROM sys.certificates WHERE name = 'cert_respaldo_ddjj')
  CREATE CERTIFICATE cert_respaldo_ddjj WITH SUBJECT = 'Cifrado de respaldos ddjj';
GO
-- Exportar el certificado y guardarlo FUERA de los respaldos (sin él no se puede restaurar):
-- BACKUP CERTIFICATE cert_respaldo_ddjj TO FILE = N'__RUTA_RESPALDO__\cert_respaldo_ddjj.cer'
--   WITH PRIVATE KEY (FILE = N'__RUTA_RESPALDO__\cert_respaldo_ddjj.pvk', ENCRYPTION BY PASSWORD = N'__CLAVE_CERTIFICADO__');

-- 2) Comandos manuales equivalentes a los de src/respaldo.py
-- BACKUP DATABASE [ddjj] TO DISK = N'__RUTA_RESPALDO__\ddjj_completo.bak'
--   WITH INIT, CHECKSUM, COMPRESSION, MAXTRANSFERSIZE = 131072,
--        ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = cert_respaldo_ddjj);
-- BACKUP DATABASE [ddjj] TO DISK = N'__RUTA_RESPALDO__\ddjj_dif.bak'
--   WITH DIFFERENTIAL, INIT, CHECKSUM, COMPRESSION, MAXTRANSFERSIZE = 131072,
--        ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = cert_respaldo_ddjj);
-- RESTORE VERIFYONLY FROM DISK = N'__RUTA_RESPALDO__\ddjj_completo.bak' WITH CHECKSUM;

-- 3) Restauración de prueba (sobre una base temporal) -> evidencia para el Anexo
-- RESTORE DATABASE ddjj_test FROM DISK = N'...\ddjj_completo.bak' WITH MOVE 'ddjj' TO N'...\ddjj_test.mdf',
--   MOVE 'ddjj_log' TO N'...\ddjj_test.ldf', NORECOVERY, REPLACE;      -- si hay diferencial
-- RESTORE DATABASE ddjj_test FROM DISK = N'...\ddjj_dif.bak' WITH RECOVERY;
GO
