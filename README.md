# lex-mx-completo

**El acervo jurídico mexicano completo, descargable y automatizable.**

> 35,132 ordenamientos estatales + 317 federales. Todos los estados, no solo los que
> el portal publica en su portada.

## Por qué existe

[`lex-mx`](https://github.com/ingteranalvarez/lex-mx) hizo un trabajo excelente: convirtió
a Markdown las 317 leyes federales de la Cámara de Diputados, con actualización diaria.
Pero su fuente —LeyesBiblio— **solo cubre derecho federal**. No incluye derecho estatal,
reglamentos del Ejecutivo, normas oficiales, tratados ni jurisprudencia.

Y el portal oficial (Orden Jurídico Nacional) marca 20 de los 32 estados como
`liberado=no`, lo que sugiere que su derecho no está publicado.

**No es cierto.** Los datos sí están. Este proyecto los descarga.

## Alcance medido

Verificado contra el servidor real (`compilacion.ordenjuridico.gob.mx`):

| Estado | Ordenamientos | | Estado | Ordenamientos |
|---|---:|---|---|---:|
| Morelos | 5,687 | | Nuevo León | 569 |
| Querétaro | 5,639 | | Veracruz | 491 |
| Michoacán | 3,172 | | Baja California Sur | 489 |
| Guerrero | 2,688 | | Campeche | 485 |
| Estado de México | 2,247 | | Tamaulipas | 436 |
| Colima | 1,736 | | Coahuila | 398 |
| Yucatán | 1,517 | | Aguascalientes | 395 |
| Guanajuato | 1,422 | | San Luis Potosí | 323 |
| Sonora | 1,325 | | Chihuahua | 213 |
| Nayarit | 922 | | Oaxaca | 209 |
| Puebla | 833 | | Sinaloa | 171 |
| Jalisco | 806 | | Baja California | 69 |
| Tabasco | 753 | | Quintana Roo | 58 |
| Hidalgo | 745 | | Zacatecas | 47 |
| Chiapas | 696 | | Durango | 1 |
| Tlaxcala | 590 | | **Ciudad de México** | **0** |

**Total estatal: 35,132.** La Ciudad de México es el único estado sin datos en esta fuente.

## Resultado de la extracción

Estado real del corpus tras la descarga completa:

| Concepto | Documentos |
|---|---:|
| Ordenamientos catalogados | **35,132** |
| Descargados | **28,082** |
| Sin documento en la fuente | **7,027** |
| Pendientes | ~23 |
| **Cobertura** | **99.93 %** |

Los 7,027 "sin documento" no son un fallo: la ficha del ordenamiento existe en el
catálogo, pero SEGOB nunca publicó el archivo. Se detectan y se marcan solos
(`sin_documento: true`) para no reintentarlos en cada pasada.

## Conversión a Markdown

`convertir_md.py` produce un `.md` por ordenamiento con frontmatter YAML:

```
  crudo (.doc):  15 GB
  markdown:     1.7 GB   (9× más compacto)
```

Los `.doc` vienen en dos formatos mezclados y hay que detectarlos por firma binaria:

- **ZIP** (`PK\x03\x04`) — docx disfrazado de `.doc`; se extrae `word/document.xml`
- **OLE2** (`\xd0\xcf\x11\xe0...`) — `.doc` binario de Word 2003; se usa `catdoc`

### Documentos escaneados

Algunos ordenamientos (resoluciones de tribunales, protocolos) **están escaneados**:
el `.docx` trae el contenido como imágenes JPEG y `word/document.xml` casi vacío
—hay casos con 28 caracteres de texto y 55 imágenes—. Esos no se pueden convertir
extrayendo texto.

`ocr_escaneados.py` los detecta (poco texto + imágenes embebidas) y les pasa
`tesseract` en español. El `.md` resultante se marca con `ocr: true` y una nota,
para que quien consuma el corpus sepa que el texto viene de reconocimiento.

### Archivos dañados

Si un `.docx` llega truncado, `zipfile` lanza `BadZipFile`. `reparar_faltantes.py`
los clasifica (`corrupto` / `escaneado` / `ok`), borra los dañados —el scraper los
vuelve a bajar en la siguiente pasada— y aplica OCR a los escaneados.

```
python3 convertir_md.py       # .doc -> .md
python3 ocr_escaneados.py     # OCR de los escaneados
python3 reparar_faltantes.py  # diagnóstico (agrega --aplicar para ejecutar)
```

## Cómo funciona

La página del portal carga su contenido en un iframe hacia otro servidor. El pipeline real:

```
  1. listPoder3.php?edo=N          -> enumera todos los ordenamientos de un estado
  2. fichaOrdenamiento2.php?id=X   -> metadatos (tipo, fecha, estatus, título)
  3. obtenerdoc.php?path=...       -> descarga el documento (.doc / .pdf)
```

## Uso

```bash
pip install curl_cffi

# un estado completo
python3 descargar.py 14          # Jalisco

# con límite, para probar
python3 descargar.py 14 50       # primeros 50 de Jalisco

# todos los estados (horas)
python3 descargar.py todos
```

Salida en `datos/<estado>/` — un documento por ordenamiento más `_index.json` con
los metadatos. La descarga es **reanudable**: lo ya bajado se salta.

Variables:

- `LEX_SALIDA` — directorio de salida (por defecto `~/lex-mx-completo/datos`)

## Estructura de los datos

```
datos/
  jalisco/
    _index.json
    12345--Ley-Organica-del-Poder-Legislativo.doc
    12346--Codigo-Civil-del-Estado-de-Jalisco.doc
```

Cada entrada de `_index.json`:

```json
{
  "id": "12345",
  "titulo": "Ley Orgánica del Poder Legislativo",
  "tipo": "Ley",
  "fecha_publicacion": "15 de Julio de 2017",
  "estatus": "Vigente",
  "ambito": "Estatal",
  "poder": "Legislativo",
  "localidad": "Jalisco",
  "doc_path": "/Documentos/ESTADO/JALISCO/o12345.doc",
  "archivo": "12345--Ley-Organica-del-Poder-Legislativo.doc",
  "bytes": 70260
}
```

## Fuente y base legal

Fuente: [Orden Jurídico Nacional](http://www.ordenjuridico.gob.mx/), Secretaría de
Gobernación, vía `compilacion.ordenjuridico.gob.mx`.

El texto de las leyes publicado en el DOF es de **dominio público**
(Art. 14, Ley Federal del Derecho de Autor): su redistribución está permitida.
El valor agregado aquí es la extracción, estructura y automatización.

## Diagnóstico previo

El servidor tiene detalles que hay que conocer:

- **Codificación mixta.** Declara UTF-8 pero manda bytes fuera de rango en los acentos.
  Se decodifica a cp1252 cuando UTF-8 estricto falla.
- **Caracteres rotos en el propio HTML.** El encabezado viene como `Ficha t\ufffdcnica`,
  así que el emparejado tiene que ser tolerante.
- **Los documentos son `.doc`**, no PDF. Se convierten con LibreOffice si se necesitan
  en otro formato.
- **El `liberado=si/no` de la portada no refleja la disponibilidad real.** Los 20 estados
  marcados como no liberados sí tienen datos en el servidor de compilación.

## Aviso

Extracción automatizada **best-effort**. **No es una fuente oficial.** Para efectos
legales consulta siempre el texto publicado en el
[DOF](https://www.dof.gob.mx/) o el periódico oficial de cada estado.

## Licencia

- Código: **MIT**
- Texto de las leyes: **dominio público**
