# Partidos libres con decisiones por contexto: qué cambió y qué necesita cada quien

Rama `feature/generador-decisiones`, del integrante 1, sacada de `feature/22-jugadores-dinamica`. Es la propuesta de `propuesta-decisiones.md`: el nivel A más el "B ligero" y los penales.

| Commit | Qué hace |
| --- | --- |
| `Generator: free matches where players decide from the play` | El generador de decisiones (`generator/decisions.py`), las tácticas (`generator/tactics.json`) y sus pruebas |
| `Contract and positions: penalties in free matches` | `set_piece: "penalty"` en el contrato y su acomodo en las posiciones |
| `Docs and data: ...` | `docs/formulas.md` sección 13, este aviso y el partido libre de muestra regenerado |

## En resumen

- **El demo `m001` no cambia: es idéntico evento por evento.** Sus órdenes, sus pruebas y el video siguen valiendo. La CI y `tests/test_decisions.py` lo comprueban.
- **Lo nuevo solo aplica a los partidos libres** (`--script free`): ahí no hay guion, y cada decisión sale de la jugada.
- **Nadie tiene que cambiar nada para que funcione.** Todas las pruebas del motor pasan (99).

## Qué cambió en los partidos libres

| Antes | Ahora |
| --- | --- |
| Quien presionaba o recogía un balón suelto se elegía por su zona fija, y a veces cruzaba media cancha: 31% de las presiones y 33% de los balones sueltos los hacía alguien que no era de los 2 más cercanos | El generador sabe dónde está cada bloque: 15% y 14% |
| El balón suelto esperaba unos 4 s | Lo recoge el más cercano cuando llega: unos 2 s |
| Solo cerca del arco, tiraba 3 de cada 10 veces | Tira según la ocasión: con 0.35 xG o más y sin presión, 94% |
| El 88% de los pases desde el área iba hacia atrás | 49%. Busca al compañero mejor ubicado |
| Faltas en el área cobradas como tiro libre | Son raras, y cada una es **penal**: unos 0.3 por partido, como en la Premier League |
| Los perfiles no existían | Salen de la **carta** de cada jugador en `mocks/teams.json` |
| El marcador no cambiaba nada | Cambia el ritmo, nunca la puntería: el que gana la guarda, el que pierde va más directo pero contra un área llena |

**Marcadores, en 200 partidos libres:** 2.9 goles de promedio, 3.5% de 0-0, un solo partido de 8 goles y ninguno de más. Todas las métricas de realismo siguen en rango.

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

Para ver también los gráficos, con los textos de plantilla de los agentes y sin llamadas al modelo:

```powershell
python -m baja_agents run --insights data/free-seed2/insights.json --offline
```

Ese `overlays.json` es solo para verlo en local: no se sube.

Para generar otro partido libre, por ejemplo la semilla 126, que trae un penal y una asistencia invisible:

```powershell
python -m baja_insights generate --seed 126 --script free --match-id f126 --out data/f126/events.jsonl
python -m baja_insights analyze --events data/f126/events.jsonl --out data/f126/insights.json
python -m baja_insights positions --events data/f126/events.jsonl --script free --out data/f126/positions.json
```

## Pendiente para después

- **Pasar `m001` al generador de decisiones.** Ahí sí cambia el partido de demo, y hay que regenerar las órdenes, ajustar las pruebas que suponen el 1-1 y rehacer el guion del video.
- **El nivel B:** que las posiciones se simulen primero y las decisiones salgan de ellas.
- **Empates:** rondan el 21% al 30% según la muestra. En la Premier League son un 23% a 25%.
- **La asistencia invisible "pura":** el motor la encuentra en algunos partidos libres, pero casi siempre el que corrió ya había tocado el balón antes en esa posesión.
