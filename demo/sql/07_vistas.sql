-- Vistas del panel. Marcador __SAL__: sal ASCII de los seudónimos (se reemplaza al ejecutar; no commitear el script reemplazado).
-- vw_*       : identificación completa (uso autorizado en organismos de control)
-- cluster_local: numeración del clúster dentro de cada ejercicio (cluster_dbscan es único entre ejercicios; -1 = ruido)
-- vw_demo_*  : seudónimos (video, capturas y anexos del trabajo)
CREATE OR ALTER VIEW resultados.vw_resultado_vigente AS
SELECT r.*, CASE WHEN e.tipo = 'ajuste' THEN 'ajuste' ELSE 'puntuacion' END AS origen_score
FROM resultados.resultado_modelo r
JOIN resultados.ejecucion_modelo e ON e.id_ejecucion = r.id_ejecucion AND e.estado = 'ok'
WHERE r.id_ejecucion = (SELECT MAX(id_ejecucion) FROM resultados.ejecucion_modelo WHERE estado = 'ok' AND tipo = 'ajuste')
   OR e.id_ejecucion_base = (SELECT MAX(id_ejecucion) FROM resultados.ejecucion_modelo WHERE estado = 'ok' AND tipo = 'ajuste');
GO
CREATE OR ALTER VIEW resultados.vw_ranking AS
SELECT r.id_hecho, fu.cuit, fu.apellido_nombre AS funcionario, o.organismo, o.actividad_principal_ambito AS ambito,
       t.ejercicio_fiscal AS ejercicio, r.score_anomalia, r.es_ruido, r.cluster_dbscan, CASE WHEN r.cluster_dbscan = -1 THEN -1 ELSE r.cluster_dbscan - MIN(CASE WHEN r.cluster_dbscan >= 0 THEN r.cluster_dbscan END) OVER (PARTITION BY t.ejercicio_fiscal) END AS cluster_local, r.origen_score, r.fecha_ejecucion,
       f.variacion_patrimonial, f.ratio_patrimonio_ingresos, f.sin_ingresos_declarados, f.total_bienes_final
FROM resultados.vw_resultado_vigente r
JOIN oro.fact_patrimonio f ON f.id_hecho = r.id_hecho
JOIN oro.dim_funcionario fu ON fu.id_funcionario = f.id_funcionario
JOIN oro.dim_organismo o ON o.id_organismo = f.id_organismo
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo;
GO
CREATE OR ALTER VIEW resultados.vw_demo_ranking AS
SELECT r.id_hecho,
       'F-' + LEFT(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT('__SAL__', fu.cuit)), 2), 10) AS seudonimo,
       o.organismo, o.actividad_principal_ambito AS ambito, t.ejercicio_fiscal AS ejercicio,
       r.score_anomalia, r.es_ruido, r.cluster_dbscan, CASE WHEN r.cluster_dbscan = -1 THEN -1 ELSE r.cluster_dbscan - MIN(CASE WHEN r.cluster_dbscan >= 0 THEN r.cluster_dbscan END) OVER (PARTITION BY t.ejercicio_fiscal) END AS cluster_local, r.origen_score, r.fecha_ejecucion,
       f.variacion_patrimonial, f.ratio_patrimonio_ingresos, f.sin_ingresos_declarados, f.total_bienes_final
FROM resultados.vw_resultado_vigente r
JOIN oro.fact_patrimonio f ON f.id_hecho = r.id_hecho
JOIN oro.dim_funcionario fu ON fu.id_funcionario = f.id_funcionario
JOIN oro.dim_organismo o ON o.id_organismo = f.id_organismo
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo;
GO
CREATE OR ALTER VIEW resultados.vw_evolucion AS
SELECT f.id_hecho, fu.cuit, fu.apellido_nombre AS funcionario, t.ejercicio_fiscal AS ejercicio,
       f.total_bienes_final, f.total_deudas_final, f.total_ingreso_neto_c1234 AS ingresos,
       f.variacion_patrimonial, r.score_anomalia, r.es_ruido
FROM oro.fact_patrimonio f
JOIN oro.dim_funcionario fu ON fu.id_funcionario = f.id_funcionario
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo
LEFT JOIN resultados.vw_resultado_vigente r ON r.id_hecho = f.id_hecho
WHERE f.es_analizada = 1;
GO
CREATE OR ALTER VIEW resultados.vw_demo_evolucion AS
SELECT f.id_hecho,
       'F-' + LEFT(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT('__SAL__', fu.cuit)), 2), 10) AS seudonimo,
       t.ejercicio_fiscal AS ejercicio, f.total_bienes_final, f.total_deudas_final,
       f.total_ingreso_neto_c1234 AS ingresos, f.variacion_patrimonial, r.score_anomalia, r.es_ruido
FROM oro.fact_patrimonio f
JOIN oro.dim_funcionario fu ON fu.id_funcionario = f.id_funcionario
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo
LEFT JOIN resultados.vw_resultado_vigente r ON r.id_hecho = f.id_hecho
WHERE f.es_analizada = 1;
GO
CREATE OR ALTER VIEW resultados.vw_modelo AS
SELECT * FROM resultados.ejecucion_modelo
WHERE id_ejecucion = (SELECT MAX(id_ejecucion) FROM resultados.ejecucion_modelo WHERE estado = 'ok' AND tipo = 'ajuste');
GO
CREATE OR ALTER VIEW resultados.vw_modelo_componentes AS
SELECT m.id_ejecucion, CAST(j.[key] AS INT) + 1 AS componente, CAST(j.[value] AS FLOAT) AS varianza_explicada
FROM resultados.vw_modelo m
CROSS APPLY OPENJSON(m.varianza_por_componente) j;
GO
CREATE OR ALTER VIEW resultados.vw_filtros AS
SELECT DISTINCT o.organismo, o.actividad_principal_ambito AS ambito, t.ejercicio_fiscal AS ejercicio
FROM oro.fact_patrimonio f
JOIN oro.dim_organismo o ON o.id_organismo = f.id_organismo
JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo
WHERE f.es_analizada = 1;
GO
