-- Ejecutar UNA VEZ en SSMS (conectado a master), antes de correr el pipeline. No lo ejecuta run_pipeline.
IF DB_ID('ddjj') IS NULL CREATE DATABASE ddjj;
GO
ALTER DATABASE ddjj SET RECOVERY SIMPLE;
GO
