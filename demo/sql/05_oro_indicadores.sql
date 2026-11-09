-- Indicadores de riesgo patrimonial del ejercicio (ANIO). Si falta un importe, el indicador queda en NULL.
UPDATE f SET
  variacion_patrimonial = f.total_bienes_final - f.total_bienes_inicio,
  sin_ingresos_declarados = CASE WHEN f.total_ingreso_neto_c1234 IS NULL THEN NULL
                                 WHEN f.total_ingreso_neto_c1234 > 0 THEN 0 ELSE 1 END,
  ratio_patrimonio_ingresos = CASE WHEN f.total_ingreso_neto_c1234 > 0
        THEN CAST(f.total_bienes_final - f.total_bienes_inicio AS FLOAT) / CAST(f.total_ingreso_neto_c1234 AS FLOAT)
        END
FROM oro.fact_patrimonio f
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo
WHERE t.ejercicio_fiscal = __ANIO__;
GO
