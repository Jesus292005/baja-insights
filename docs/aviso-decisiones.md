# Partidos libres con decisiones por contexto: qué cambió y qué necesita cada quien

Rama `feature/generador-decisiones`, del integrante 1, sacada de `feature/22-jugadores-dinamica`. Es la propuesta de `propuesta-decisiones.md`: el nivel A más el "B ligero" y los penales.

| Commit | Qué hace |
| --- | --- |
| `Generator: free matches where players decide from the play` | El generador de decisiones (`generator/decisions.py`), las tácticas (`generator/tactics.json`) y sus pruebas |
| `Contract and positions: penalties in free matches` | `set_piece: "penalty"` en el contrato y su acomodo en las posiciones |
| `Docs and data: ...` | `docs/formulas.md` sección 13, este aviso y el partido libre de muestra regenerado |
| `Generator: read the press, shoot first time, counter-attacks` | Soltar el balón antes de la presión o aguantarla con riesgo, tiro de primera, contragolpes, centros y puntería más reales |

## En resumen

- **El demo `m001` no cambia: es idéntico evento por evento.** Sus órdenes, sus pruebas y el video siguen valiendo. La CI y `tests/test_decisions.py` lo comprueban.
- **Lo nuevo solo aplica a los partidos libres** (`--script free`): ahí no hay guion, y cada decisión sale de la jugada.
- **Nadie tiene que cambiar nada para que funcione.** Todas las pruebas del motor pasan (103).

## Qué cambió en los partidos libres

| Antes | Ahora |
| --- | --- |
| Quien presionaba o recogía un balón suelto se elegía por su zona fija, y a veces cruzaba media cancha: 31% de las presiones y 33% de los balones sueltos los hacía alguien que no era de los 2 más cercanos | El generador sabe dónde está cada bloque y dónde actuó cada jugador hace un momento: 18% y 14% |
| El presionado siempre se dejaba llegar | El 59% la suelta antes de que llegue el rival, con un pase que sale bien el 83% de las veces. El que lo espera pierde el balón el 53% de las veces: entrada, robo, regate perdido o mal pase |
| Casi nadie jugaba de primera (3%) | 15% de los pases sin presión son de primera |
| Tiraba 4 s después de recibir | El 59% de los remates sale en 2 s o menos: **tiro de primera**, con 10% menos de xG |
| Centros completados: 49% | 31%: la defensa despeja casi todos |
| Casi no había contragolpes (0.6%) | 1.8% de las recuperaciones en campo propio acaba en remate en 15 s |
| 44% de los remates iba a puerta | 33%, como en la Premier League |
| El balón suelto esperaba unos 4 s | Lo recoge el más cercano cuando llega: unos 2 s |
| Solo cerca del arco, tiraba 3 de cada 10 veces | Tira según la ocasión: con 0.35 xG o más y sin presión, casi siempre |
| El 88% de los pases desde el área iba hacia atrás | 49%. Busca al compañero mejor ubicado |
| Faltas en el área cobradas como tiro libre | Son raras, y cada una es **penal**: unos 0.3 por partido, como en la Premier League |
| Los perfiles no existían | Salen de la **carta** de cada jugador en `mocks/teams.json` |
| El marcador no cambiaba nada | Cambia el ritmo, nunca la puntería: el que gana la guarda, el que pierde va más directo pero contra un área llena |

**Marcadores, en 200 partidos libres:** 3.0 goles de promedio, 5% de 0-0, 1.5% de partidos de 8 goles y ninguno de más. Todas las métricas de realismo siguen en rango.

## Contrato

- `set_piece` acepta `"penalty"`, y solo en un `shot`: el remate desde el punto, con xG 0.76.
- En `positions.json`, `set_pieces[].kind` puede ser `"penalty"`: portero en su línea, el que patea en el punto y los demás fuera del área y del arco.
- Nada que ya existía deja de validar. Detalle en `docs/cambios-contrato-v1.1.md`.

## Qué necesita cada quien

### Diego, agentes

- **Nada obligatorio.** Los agentes no leen `set_piece`, y `m001` no cambia, así que sus órdenes siguen valiendo.
- `data/free-seed2` (partido `f002`) se regeneró. Si alguna prueba usa ese partido, puede cambiar; la CI lo dirá.
- **Opcional:** que el narrador diga "de penal" cuando el remate del gol trae `set_piece: "penalty"`.

### luismar, interfaz

- **Nada obligatorio.** La web ya lee `kind` como texto, y el balón parado rápido funciona igual con el penal.
- **Opcional:** una etiqueta "Penal" / "Penalty" para `kind: "penalty"`.

## Cómo ver un partido libre en la web

La web necesita un `overlays.json` en la carpeta del partido. Para verlo solo con la cancha y el marcador, sin gráficos, en PowerShell:

```powershell
cd C:\Users\jesus\Documents\UABC\Baja-Insights\baja-insights
Set-Content -Path data\free-seed2\overlays.json -Value '[]' -NoNewline -Encoding ascii
cd web
$env:BAJA_MATCH = "free-seed2"
npm run dev
```

Para ver también los gráficos, con los textos de plantilla de los agentes y sin llamadas al modelo, en lugar del `Set-Content` y desde la carpeta del repo (necesita las dependencias de `agents/requirements.txt`):

```powershell
python -m baja_agents run --insights data/free-seed2/insights.json --offline
```

Ese `overlays.json` es solo para verlo en local: no se sube. Lo mismo para las carpetas de otros partidos que generes.

El partido de muestra (`free-seed2`) quedó 0-0. Para ver uno con goles, por ejemplo la semilla 91, un 2-2 con un penal y una asistencia invisible:

```powershell
python -m baja_insights generate --seed 91 --script free --match-id f091 --out data/f091/events.jsonl
python -m baja_insights analyze --events data/f091/events.jsonl --out data/f091/insights.json
python -m baja_insights positions --events data/f091/events.jsonl --script free --out data/f091/positions.json
Set-Content -Path data\f091\overlays.json -Value '[]' -NoNewline -Encoding ascii
```

## Pendiente para después

- **Pasar `m001` al generador de decisiones.** Ahí sí cambia el partido de demo, y hay que regenerar las órdenes, ajustar las pruebas que suponen el 1-1 y rehacer el guion del video.
- **El nivel B:** que las posiciones se simulen primero y las decisiones salgan de ellas.
- **Empates:** 22% en los primeros 100 partidos libres, pero varía con la muestra. En la Premier League son un 23% a 25%.
- **La asistencia invisible "pura":** el motor la encuentra en algunos partidos libres, pero casi siempre el que corrió ya había tocado el balón antes en esa posesión.
