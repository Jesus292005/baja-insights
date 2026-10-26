# Coordenadas en la cadena del gol: qué cambió y qué necesita cada quien

Rama `motor/goal-chain-coords`, del integrante 1, sobre `motor/mocks-v1.1`. Agrega lo necesario para dibujar en la cancha la jugada de cada gol, en especial el 1-1: la recuperación de Cota, el desmarque de Torres arrastrando a Cárdenas, el pase de Salgado que rompe 2 líneas y el remate de Ramírez.

**Toca `mocks/` y `contracts/`, así que necesita el visto bueno de Diego y de luismar antes del merge** (ver `CONTRIBUTING.md`).

---

## Qué no cambia

- **Ningún campo existente cambia ni se renombra.** Todo es opcional y se agrega a v1.1. Lo que validaba antes sigue validando, incluido el `data/m001/overlays.json` actual.
- **La historia de `m001` es la misma.** Mismos eventos, mismos `event_id`, mismos insights, créditos, prioridades y textos. Lo único que cambia en `data/` son los campos nuevos de abajo.
- **Ni `agents/` ni `web/`.** Lo que cada quien debe cambiar está al final.

---

## Qué cambió

### 1. Cada eslabón de la cadena trae `start` y `end`

En `goal_chain.facts.chain` y, por lo tanto, en `goal_analysis.data.chain_detail`, porque los agentes ya copian el eslabón completo.

| Campo | Qué es |
| --- | --- |
| `start` | Dónde ocurrió la acción, `[x, y]` en metros, copiado del evento |
| `end` | A dónde fue el pase, el tiro o el desmarque. `null` en recuperaciones |
| `dragged_defender` | Solo en desmarques: el defensor arrastrado |
| `dragged_defender_start`, `dragged_defender_end` | Solo en desmarques guionizados: dónde estaba el defensor y a dónde lo llevó el desmarque |

Así queda el desmarque de Torres en el 1-1:

```json
{"event_id": 973, "player": "J. Torres", "action": "desmarque y arrastre de marca", "credit": 0.25,
 "t_s": 3778, "type": "off_ball_run", "lines_broken": 0, "start": [78, 10], "end": [92, 26],
 "dragged_defender": "G. Cárdenas", "dragged_defender_start": [90, 37], "dragged_defender_end": [92, 27.7]}
```

Cárdenas se mueve 9.5 m, lo mismo que `space_opened_m`, y termina pegado a Torres. El hueco que deja es donde Ramírez recibe el pase, en `[93, 42]`.

### 2. El evento del desmarque trae al defensor

`off_ball_run` acepta `dragged_defender_start` y `dragged_defender_end` opcionales. Solo los trae el desmarque guionizado de Torres, en `mocks/events_sample.json` (evento 1353), y de ahí el generador lo copia a `data/m001/events.jsonl` (evento 973). En los partidos libres no hay coordenadas del defensor, así que el eslabón solo trae `dragged_defender`.

### 3. Archivos

| Archivo | Cambio |
| --- | --- |
| `src/baja_insights/engine/core.py` | `chain_link` copia `start`, `end` y los datos del defensor |
| `contracts/*.schema.json` y `contracts/README.md` | Los campos nuevos, todos opcionales |
| `mocks/events_sample.json(l)` | Coordenadas de Cárdenas en el evento 1353 |
| `mocks/insights_sample.json` | Cadenas de `i02` e `i11` |
| `mocks/overlays_sample.json` | `chain_detail` de `o005` a `o008` y de `o037` a `o040` |
| `mocks/chat_tools_sample.json` | Ejemplo de `get_goal_chain`, que devuelve la misma forma que los `facts` |
| `data/m001/events.jsonl` e `insights.json`, `data/free-seed2/insights.json` | Regenerados, solo con los campos nuevos |
| `tests/` | Pruebas de que cada eslabón copia las coordenadas de su evento y de que Cárdenas se mueve lo que dice `space_opened_m` |

---

## Cómo se dibuja

- **Cancha** de 105 × 68 m con el origen en la esquina **inferior** izquierda. Bahía FC ataca siempre hacia x = 105 y Real Cardón hacia x = 0, en los dos tiempos.
- **En el SVG de 1050 × 680** (`PitchBackdrop`), un punto `[x, y]` va en `(x · 10, (68 − y) · 10)`. Hay que invertir el eje y, porque en SVG crece hacia abajo. Si solo se multiplica por 10, la jugada sale reflejada y Torres aparece en la banda contraria.
- **Solo se dibuja a quien participa.** No hay posiciones de los 22 jugadores: un jugador que no toca el balón no tiene coordenadas en ese momento. Se dibujan los eslabones de la cadena y, si viene, el defensor arrastrado. Nada más.
- **Propuesta de código visual:**
  - Línea continua de `start` a `end` para la acción de cada eslabón.
  - Línea punteada para el tramo del balón que no está en la cadena: del último eslabón con balón al `start` del siguiente con balón. El desmarque se salta, porque Torres no toca el balón. En el 1-1, la punteada va de la recuperación de Cota a Salgado, no a Torres.
  - Un punto para la recuperación, porque su `end` es `null`.
  - Flecha del defensor de `dragged_defender_start` a `dragged_defender_end` en otro color, con la etiqueta «+9.5 m de espacio».
  - Animar los eslabones en orden de `t_s` y mostrar el crédito de cada uno.
- **Si no vienen `start` y `end`**, como en órdenes viejas, se muestra la cadena como hoy, sin cancha.

---

## Qué necesita cada quien

### Diego, agentes

- **Regenerar `data/m001/overlays.json`** con los insights nuevos. `data_for` ya copia el eslabón completo, así que no hay que cambiar código para que lleguen las coordenadas. Las órdenes `o005` a `o008` y `o037` a `o040` del mock muestran cómo deben quedar.
- **Una línea en `agents/baja_agents/checks.py`:** agregar `"start"`, `"end"`, `"dragged_defender_start"` y `"dragged_defender_end"` a `UI_ONLY_FACTS`. Si no, las coordenadas entran a `allowed_numbers` y el verificador dejaría pasar un número inventado como «92» solo porque coincide con una coordenada.
- **Volver a desplegar `baja-stream`** después del merge, para que el modo en vivo también traiga las coordenadas. Viajan dentro de la orden, así que en vivo llegan igual que en la repetición.

### luismar, interfaz

- **Agregar a `ChainLink`** en `web/src/contracts/overlay.ts` los campos opcionales `type`, `lines_broken`, `cross`, `start`, `end`, `dragged_defender`, `dragged_defender_start` y `dragged_defender_end`.
- **Dibujar la jugada** sobre `PitchBackdrop` en `goal_analysis`, con la conversión de arriba. Se puede probar desde ya con `mocks/overlays_sample.json`, órdenes `o037` a `o040`.
