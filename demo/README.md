# Detección de anomalías patrimoniales en declaraciones juradas (2015-2024)

Prototipo del Trabajo Final de Grado (Licenciatura en Ciencia de Datos, Universidad Siglo 21).
Pipeline ETL Bronce → Plata → Oro (esquema estrella en SQL Server), modelo no supervisado (PCA + DBSCAN) y panel en Power BI.
Los datos de entrada son públicos (archivos anuales 2015-2024 del Ministerio de Justicia, https://datos.gob.ar/dataset/declaraciones-juradas-patrimoniales-integrales) y se descargan con el propio pipeline.
**El repositorio no incluye datos, respaldos, credenciales ni resultados nominales.**

## Requisitos
Python 3.10+, SQL Server (Developer), ODBC Driver 17 o 18 for SQL Server, Power BI Desktop, Git.

## Instalación
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # completar credenciales y la sal de seudónimos
```
En SQL Server, ejecutar `sql/crear_base.sql` (crea la base `ddjj`) o, a mano: `CREATE DATABASE ddjj;  ALTER DATABASE ddjj SET RECOVERY SIMPLE;`
Editar `config/config.yaml`: URLs de descarga de cada ejercicio (datos.gob.ar) y rutas de respaldo.

## Ejecución (orden)
Todos los comandos se corren desde esta carpeta (`demo/`). Cada paso requiere que los anteriores hayan terminado bien.

| # | Paso | Comando | Archivos que intervienen | Resultado |
|---|------|---------|--------------------------|-----------|
| 0 | Preparación | `pip install -r requirements.txt`; copiar `.env.example` a `.env`; ejecutar `sql/crear_base.sql` en SSMS | `requirements.txt`, `.env.example`, `sql/crear_base.sql`, `config/config.yaml` | Entorno listo y base `ddjj` creada |
| 1 | EDA (sin SQL Server) | abrir `notebooks/01_eda.ipynb` | `src/ingesta.py`, `src/limpieza.py` | Conteos, inválidos, figuras en `data/salidas/` |
| 2 | DDL de Bronce/Plata (solo si cambian los CSV) | `python -m tools.generar_ddl` | `tools/generar_ddl.py` | `sql/01_bronce_ddl.sql`, `sql/02_plata_ddl.sql` |
| 3 | Instalar esquemas y tablas | `python -m src.run_pipeline --paso instalar` | `sql/00`, `01`, `02`, `03`, `06` | Esquemas bronce/plata/oro/resultados |
| 4 | Descarga | `--paso descarga` (con `fuente.zip_url` completa en el config; o copiar los CSV a `data/raw`) | `src/descarga.py` | 10 CSV + `MANIFEST.json` (SHA-256) |
| 5 | Ingesta (Bronce) | `--paso ingesta` | `src/ingesta.py` | Tablas bronce, con conteo contra lo esperado |
| 6 | Limpieza (Plata) | `--paso limpieza` | `src/limpieza.py` | Tablas plata + `invalidos_<año>.csv` |
| 7 | Carga Oro | `--paso oro` | `src/carga_oro.py`, `sql/04_oro_carga.sql`, `sql/05_oro_indicadores.sql` | Esquema estrella e indicadores |
| 8 | Elegir parámetros | abrir `notebooks/02_seleccion_parametros.ipynb` | — | `eps` y `min_samples`: copiarlos a `config/config.yaml` |
| 9 | Modelo | `--paso modelo` | `src/modelo.py` | Scores en `resultados.resultado_modelo` |
| 10 | Evaluación | `--paso evaluacion` | `src/evaluacion.py` | Silhouette, estabilidad temporal y muestral, sensibilidad |
| 11 | Puntuar declaraciones nuevas (sin reajustar) | `--paso puntuar` (opcional `--anio 2025`) | `src/puntuar.py`, modelo guardado en `data/salidas/modelo_<id>.joblib` | Scores de declaraciones nuevas en `resultados.resultado_modelo` (tipo `puntuacion`) |
| 11b | Revisión cualitativa | `--paso revision` | `src/revision_cualitativa.py` | Excel de revisión (con seudónimos) |
| 12 | Vistas del panel | `--paso vistas` | `sql/07_vistas.sql` (requiere `SAL_SEUDONIMO`) | Vistas `vw_*` y `vw_demo_*` |
| 13 | Seguridad | `--paso seguridad` | `sql/08_seguridad.sql` (requiere `BI_READER_PASSWORD`) | Usuario `bi_reader` y auditoría |
| 14 | Respaldo | editar y ejecutar `sql/09_respaldo.sql` (una vez), luego `scripts/programar_respaldos.ps1` | `src/respaldo.py` | Respaldos programados y cifrados |
| 15 | Panel | abrir `powerbi/Dashboard_TFG.pbit` en Power BI Desktop, indicar el servidor y la base, y actualizar | `powerbi/Dashboard_TFG.pbit` (se conecta a las vistas `vw_demo_*`, con seudónimos) | Panel en Power BI Desktop |

Notas:
- `--paso puntuar` se usa cuando se cargan declaraciones nuevas (pasos 4 a 7 con `--anio`) y se quiere evaluarlas con el modelo ya ajustado; si se publica un ejercicio completo conviene reajustar con `--paso modelo`.
- `--paso todo` encadena los pasos 4 a 7, 9 y 10. Solo sirve si ya hiciste 3 y 8 (con `eps` y `min_samples` cargados).
- Para repetir un solo ejercicio: `--anio 2022`. Para recargar Oro desde cero: `--paso oro --reiniciar`.
- `pytest` se puede correr en cualquier momento (ver abajo).

## Pruebas
```
pytest
set DDJJ_RAW=C:\ruta\a\los\csv & pytest      # incluye las pruebas con los archivos reales; las de SQL Server se omiten sin conexión
```

## Decisiones de diseño
- Variables: bienes finales, deudas finales, ingresos netos y variación patrimonial (log, estandarizadas por ejercicio).
- PCA con todas las declaraciones analizadas (anuales); **DBSCAN se ajusta dentro de cada ejercicio** (memoria y comparación con pares).
- Score = distancia, en el espacio de componentes, al punto núcleo de DBSCAN más cercano.
- Importes con formato inválido pasan a NULL y se registran en `data/salidas/invalidos_<año>.csv`.
- Con menos de 2 clusters el Silhouette se informa como «no aplicable».

## Estructura
`config/` · `sql/` (00-09 y `crear_base.sql`) · `src/` · `tools/` · `notebooks/` · `tests/` · `powerbi/` (plantilla `.pbit`, sin datos) · `scripts/`

## Panel
La plantilla `powerbi/Dashboard_TFG.pbit` no contiene datos. Al abrirla se conecta a las vistas con seudónimos (`vw_demo_*`) y a las de métricas del modelo (`vw_modelo`, `vw_modelo_componentes`). Las medidas y la configuración de las cuatro pantallas se describen en el Anexo F del trabajo.
