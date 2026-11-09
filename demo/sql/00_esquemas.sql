-- Crear la base
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'bronce')     EXEC('CREATE SCHEMA bronce');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'plata')      EXEC('CREATE SCHEMA plata');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'oro')        EXEC('CREATE SCHEMA oro');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'resultados') EXEC('CREATE SCHEMA resultados');
