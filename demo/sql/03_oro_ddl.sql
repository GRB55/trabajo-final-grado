-- Esquema estrella
IF OBJECT_ID('oro.dim_funcionario') IS NULL
CREATE TABLE oro.dim_funcionario (
  id_funcionario  INT IDENTITY(1,1) PRIMARY KEY,
  cuit            BIGINT NOT NULL UNIQUE,
  apellido_nombre NVARCHAR(200) NULL
);
GO
IF OBJECT_ID('oro.dim_organismo') IS NULL
CREATE TABLE oro.dim_organismo (
  id_organismo               INT IDENTITY(1,1) PRIMARY KEY,
  organismo                  NVARCHAR(200) NOT NULL,
  sector                     VARCHAR(10)   NOT NULL,
  actividad_principal_ambito NVARCHAR(300) NOT NULL,
  CONSTRAINT uq_dim_organismo UNIQUE (organismo, sector, actividad_principal_ambito)
);
GO
IF OBJECT_ID('oro.dim_cargo') IS NULL
CREATE TABLE oro.dim_cargo (
  id_cargo          INT IDENTITY(1,1) PRIMARY KEY,
  cargo_normalizado NVARCHAR(400) NOT NULL UNIQUE
);
GO
IF OBJECT_ID('oro.dim_tiempo') IS NULL
CREATE TABLE oro.dim_tiempo (
  id_tiempo        INT IDENTITY(1,1) PRIMARY KEY,
  ejercicio_fiscal SMALLINT NOT NULL UNIQUE
);
GO
IF OBJECT_ID('oro.dim_tipo_dj') IS NULL
CREATE TABLE oro.dim_tipo_dj (
  id_tipo_dj                          INT IDENTITY(1,1) PRIMARY KEY,
  tipo_declaracion_jurada_id          SMALLINT NOT NULL,
  tipo_declaracion_jurada_descripcion VARCHAR(10) NOT NULL,
  CONSTRAINT uq_dim_tipo UNIQUE (tipo_declaracion_jurada_id, tipo_declaracion_jurada_descripcion)
);
GO
IF OBJECT_ID('oro.fact_patrimonio') IS NULL
CREATE TABLE oro.fact_patrimonio (
  id_hecho        BIGINT IDENTITY(1,1) PRIMARY KEY,
  dj_id           BIGINT NOT NULL UNIQUE,
  id_funcionario  INT NOT NULL REFERENCES oro.dim_funcionario(id_funcionario),
  id_organismo    INT NOT NULL REFERENCES oro.dim_organismo(id_organismo),
  id_cargo        INT NOT NULL REFERENCES oro.dim_cargo(id_cargo),
  id_tiempo       INT NOT NULL REFERENCES oro.dim_tiempo(id_tiempo),
  id_tipo_dj      INT NOT NULL REFERENCES oro.dim_tipo_dj(id_tipo_dj),
  fecha_inicio_cargo               DATE NULL,
  horas_dedicacion                 SMALLINT NULL,
  total_bienes_inicio              DECIMAL(18,2) NULL,
  total_bienes_final               DECIMAL(18,2) NULL,
  deudas_inicio                    DECIMAL(18,2) NULL,
  total_deudas_final               DECIMAL(18,2) NULL,
  diferencia_valuacion             DECIMAL(18,2) NULL,
  ingreso_neto_renta_sueldo_c1     DECIMAL(18,2) NULL,
  ingreso_neto_renta_capitales_c2  DECIMAL(18,2) NULL,
  total_ingresos_c3                DECIMAL(18,2) NULL,
  total_ingreso_neto_c1234         DECIMAL(18,2) NULL,
  variacion_patrimonial            DECIMAL(18,2) NULL,
  ratio_patrimonio_ingresos        FLOAT NULL,
  sin_ingresos_declarados          BIT NULL,
  es_analizada                     BIT NOT NULL DEFAULT 0,
  cantidad_rectificaciones         SMALLINT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_fact_tiempo_analizada' AND object_id = OBJECT_ID('oro.fact_patrimonio'))
  CREATE INDEX ix_fact_tiempo_analizada ON oro.fact_patrimonio (id_tiempo, es_analizada);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_fact_func_tiempo' AND object_id = OBJECT_ID('oro.fact_patrimonio'))
  CREATE INDEX ix_fact_func_tiempo ON oro.fact_patrimonio (id_funcionario, id_tiempo);
GO
CREATE OR ALTER VIEW oro.vw_indicadores AS
SELECT id_hecho,
       LOG(1 + CASE WHEN total_bienes_final  > 0 THEN total_bienes_final  ELSE 0 END)
     - LOG(1 + CASE WHEN total_bienes_inicio > 0 THEN total_bienes_inicio ELSE 0 END) AS variacion_relativa_log,
       ratio_patrimonio_ingresos
FROM oro.fact_patrimonio;
GO
