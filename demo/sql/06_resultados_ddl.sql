-- ejecucion_modelo es metadata técnica de ejecución (como el log).
IF OBJECT_ID('resultados.ejecucion_modelo') IS NULL
CREATE TABLE resultados.ejecucion_modelo (
  id_ejecucion            BIGINT IDENTITY(1,1) PRIMARY KEY,
  fecha                   DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
  estado                  VARCHAR(10) NOT NULL,        -- en_curso | ok | error | invalida
  tipo                    VARCHAR(10) NOT NULL DEFAULT 'ajuste',  -- ajuste | puntuacion
  id_ejecucion_base       BIGINT NULL,                  -- en una puntuación: el ajuste que se aplicó
  ruta_modelo             NVARCHAR(260) NULL,           -- archivo con PCA, estadísticos y puntos núcleo del ajuste
  eps                     FLOAT NULL,
  min_samples             INT NULL,
  n_componentes           INT NULL,
  varianza_explicada      FLOAT NULL,
  varianza_por_componente NVARCHAR(400) NULL,           -- JSON
  proporcion_ruido        FLOAT NULL,
  silhouette              FLOAT NULL,                   -- NULL = no aplicable
  n_evaluadas             INT NULL,
  n_no_evaluadas          INT NULL,
  semilla                 INT NULL,
  version_codigo          VARCHAR(60) NULL,
  estabilidad_json        NVARCHAR(MAX) NULL
);
GO
IF OBJECT_ID('resultados.resultado_modelo') IS NULL
CREATE TABLE resultados.resultado_modelo (
  id_resultado    BIGINT IDENTITY(1,1) PRIMARY KEY,
  id_ejecucion    BIGINT NOT NULL,
  id_hecho        BIGINT NOT NULL REFERENCES oro.fact_patrimonio(id_hecho),
  componentes_pca NVARCHAR(400) NULL,
  cluster_dbscan  SMALLINT NULL,
  es_ruido        BIT NOT NULL,
  score_anomalia  FLOAT NOT NULL,
  fecha_ejecucion DATETIME2 NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_resultado_ejec_score' AND object_id = OBJECT_ID('resultados.resultado_modelo'))
  CREATE INDEX ix_resultado_ejec_score ON resultados.resultado_modelo (id_ejecucion, score_anomalia DESC) INCLUDE (id_hecho, es_ruido);
GO
