-- Carga de un ejercicio (ANIO) desde plata a oro. Idempotente.
-- Dimensiones
INSERT INTO oro.dim_funcionario (cuit, apellido_nombre)
SELECT x.cuit, x.funcionario_normalizado
FROM (SELECT cuit, funcionario_normalizado,
             ROW_NUMBER() OVER (PARTITION BY cuit ORDER BY dj_id DESC) AS rn
      FROM plata.declaraciones WHERE anio = __ANIO__) x
WHERE x.rn = 1
  AND NOT EXISTS (SELECT 1 FROM oro.dim_funcionario d WHERE d.cuit = x.cuit);
GO
INSERT INTO oro.dim_organismo (organismo, sector, actividad_principal_ambito)
SELECT DISTINCT p.organismo, p.sector_normalizado, p.actividad_principal_ambito
FROM plata.declaraciones p
WHERE p.anio = __ANIO__
  AND NOT EXISTS (SELECT 1 FROM oro.dim_organismo d
                  WHERE d.organismo = p.organismo AND d.sector = p.sector_normalizado
                    AND d.actividad_principal_ambito = p.actividad_principal_ambito);
GO
INSERT INTO oro.dim_cargo (cargo_normalizado)
SELECT DISTINCT p.cargo_normalizado
FROM plata.declaraciones p
WHERE p.anio = __ANIO__
  AND NOT EXISTS (SELECT 1 FROM oro.dim_cargo d WHERE d.cargo_normalizado = p.cargo_normalizado);
GO
INSERT INTO oro.dim_tiempo (ejercicio_fiscal)
SELECT DISTINCT p.anio FROM plata.declaraciones p
WHERE p.anio = __ANIO__
  AND NOT EXISTS (SELECT 1 FROM oro.dim_tiempo d WHERE d.ejercicio_fiscal = p.anio);
GO
INSERT INTO oro.dim_tipo_dj (tipo_declaracion_jurada_id, tipo_declaracion_jurada_descripcion)
SELECT DISTINCT COALESCE(p.tipo_declaracion_jurada_id, -1), p.tipo_dj
FROM plata.declaraciones p
WHERE p.anio = __ANIO__
  AND NOT EXISTS (SELECT 1 FROM oro.dim_tipo_dj d
                  WHERE d.tipo_declaracion_jurada_id = COALESCE(p.tipo_declaracion_jurada_id, -1)
                    AND d.tipo_declaracion_jurada_descripcion = p.tipo_dj);
GO
-- Hechos
DELETE FROM oro.fact_patrimonio
WHERE id_tiempo = (SELECT id_tiempo FROM oro.dim_tiempo WHERE ejercicio_fiscal = __ANIO__);
GO
INSERT INTO oro.fact_patrimonio
  (dj_id, id_funcionario, id_organismo, id_cargo, id_tiempo, id_tipo_dj,
   fecha_inicio_cargo, horas_dedicacion,
   total_bienes_inicio, total_bienes_final, deudas_inicio, total_deudas_final, diferencia_valuacion,
   ingreso_neto_renta_sueldo_c1, ingreso_neto_renta_capitales_c2, total_ingresos_c3, total_ingreso_neto_c1234,
   es_analizada, cantidad_rectificaciones)
SELECT p.dj_id, f.id_funcionario, o.id_organismo, c.id_cargo, t.id_tiempo, tp.id_tipo_dj,
       p.desde, p.horas_dedicacion,
       p.total_bienes_inicio, p.total_bienes_final, p.deudas_inicio, p.total_deudas_final, p.diferencia_valuacion,
       p.ingreso_neto_renta_sueldo_c1, p.ingreso_neto_renta_capitales_c2, p.total_ingresos_c3, p.total_ingreso_neto_c1234,
       p.es_analizada, p.rectificativa
FROM plata.declaraciones p
JOIN oro.dim_funcionario f ON f.cuit = p.cuit
JOIN oro.dim_organismo   o ON o.organismo = p.organismo AND o.sector = p.sector_normalizado
                          AND o.actividad_principal_ambito = p.actividad_principal_ambito
JOIN oro.dim_cargo       c ON c.cargo_normalizado = p.cargo_normalizado
JOIN oro.dim_tiempo      t ON t.ejercicio_fiscal = p.anio
JOIN oro.dim_tipo_dj    tp ON tp.tipo_declaracion_jurada_id = COALESCE(p.tipo_declaracion_jurada_id, -1)
                          AND tp.tipo_declaracion_jurada_descripcion = p.tipo_dj
WHERE p.anio = __ANIO__;
GO
