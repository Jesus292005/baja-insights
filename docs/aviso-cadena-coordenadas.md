# Coordenadas en la cadena del gol: qué cambió y qué necesita cada quien

Rama `motor/goal-chain-coords`, del integrante 1, sobre `motor/mocks-v1.1` (commit `f6e6ec8`). Agrega lo necesario para dibujar en la cancha la jugada de cada gol, en especial el 1-1: la recuperación de Cota, el desmarque de Torres arrastrando a Cárdenas, el pase de Salgado que rompe 2 líneas y el remate de Ramírez.

**Toca `mocks/` y `contracts/`, así que necesita el visto bueno de Diego y de luismar antes del merge** (ver `CONTRIBUTING.md`).

## En resumen

- Cada eslabón de `goal_chain.facts.chain` trae ahora `start` y `end` en metros. El desmarque trae además al defensor arrastrado y sus coordenadas.
- Todo es **opcional y se agrega a v1.1**. Nada se renombra y todo lo que validaba antes sigue validando.
- Los agentes ya copian el eslabón completo a `goal_analysis.data.chain_detail`, así que las coordenadas llegan solas a las órdenes, en la repetición y en vivo.
- **Diego** necesita un ajuste pequeño para que los prompts no cambien, y después regenerar las órdenes. **luismar** dibuja la jugada. Los pasos están abajo.

---

## Qué cambió

### 1. Cada eslabón de la cadena trae coordenadas

| Campo | Qué es | Cuándo viene |
| --- | --- | --- |
| `start` | Dónde ocurrió la acción, `[x, y]` en metros, copiado del evento | Siempre |
| `end` | A dónde fue el pase, el tiro o el desmarque | Siempre. Es `null` en recuperaciones |
| `dragged_defender` | El defensor arrastrado | Solo en desmarques |
| `dragged_defender_start` | Dónde estaba el defensor | Solo en desmarques guionizados |
| `dragged_defender_end` | A dónde lo llevó el desmarque | Solo en desmarques guionizados |

La cadena del 1-1 en `data/m001/insights.json` queda así:

| # | Jugador | Acción | Crédito | `start` | `end` |
| --- | --- | --- | --- | --- | --- |
| 1 | F. Cota | recuperación | 18% | `[48, 30]` | `null` |
| 2 | J. Torres | desmarque y arrastre de marca | 25% | `[78, 10]` | `[92, 26]` |
| 3 | R. Salgado | pase que rompió 2 líneas | 35% | `[70, 38]` | `[93, 42]` |
| 4 | M. Ramírez | remate | 22% | `[93, 42]` | `[105, 35]` |

Y el eslabón del desmarque completo:

```json
{"event_id": 973, "player": "J. Torres", "action": "desmarque y arrastre de marca", "credit": 0.25,
 "t_s": 3778, "type": "off_ball_run", "lines_broken": 0, "start": [78, 10], "end": [92, 26],
 "dragged_defender": "G. Cárdenas", "dragged_defender_start": [90, 37], "dragged_defender_end": [92, 27.7]}
```

Cárdenas se mueve 9.5 m, lo mismo que `space_opened_m`, y termina pegado a Torres. El hueco que deja es donde Ramírez recibe el pase, en `[93, 42]`.

### 2. El evento del desmarque trae al defensor

`off_ball_run` acepta `dragged_defender_start` y `dragged_defender_end` opcionales. Solo los trae el desmarque guionizado de Torres:

- En `mocks/events_sample.json` es el evento 1353.
- El generador lo copia tal cual a `data/m001/events.jsonl`, donde es el evento 973.

En los partidos libres no hay coordenadas del defensor, así que el eslabón solo trae `dragged_defender`.

### 3. Archivos que cambiaron

| Archivo | Cambio |
| --- | --- |
| `src/baja_insights/engine/core.py` | `chain_link` copia `start`, `end` y los datos del defensor |
| `contracts/event.schema.json`, `insight.schema.json` y `overlay.schema.json` | Los campos nuevos, todos opcionales, con su rango de cancha |
| `contracts/README.md` | Los campos nuevos y cómo dibujarlos |
| `mocks/events_sample.json` y `.jsonl` | Coordenadas de Cárdenas en el evento 1353 |
| `mocks/insights_sample.json` | Cadenas de `i02` (0-1) e `i11` (1-1) |
| `mocks/overlays_sample.json` | `chain_detail` de `o005` a `o008` y de `o037` a `o040` |
| `mocks/chat_tools_sample.json` | Ejemplo de `get_goal_chain`, que devuelve la misma forma que los `facts` |
| `data/m001/events.jsonl` e `insights.json`, `data/free-seed2/insights.json` | Regenerados |
| `tests/test_engine.py` y `tests/test_demo_story.py` | Cada eslabón copia las coordenadas de su evento, y Cárdenas se mueve lo que dice `space_opened_m` |

### 4. Qué no cambia

- **La historia de `m001` es la misma.** Mismos eventos, `event_id`, insights, créditos, prioridades y textos del motor. Se comprobó que, si a cada eslabón se le quitan los cinco campos nuevos, `insights.json` queda idéntico al anterior, en `m001` y en `free-seed2`.
- **El `data/m001/overlays.json` actual sigue validando.** Simplemente todavía no trae coordenadas.
- **No se tocó `agents/` ni `web/`.**

---

## Cómo se dibuja

- **Cancha** de 105 × 68 m, con el origen en la esquina **inferior** izquierda. Bahía FC ataca siempre hacia x = 105 y Real Cardón hacia x = 0, en los dos tiempos.
- **En el SVG de 1050 × 680** (`PitchBackdrop`), un punto `[x, y]` va en `(x · 10, (68 − y) · 10)`. Hay que invertir el eje y porque en SVG crece hacia abajo. Si solo se multiplica por 10, la jugada sale reflejada y Torres aparece en la banda contraria.
- **Solo se dibuja a quien participa.** No hay posiciones de los 22 jugadores: un jugador que no toca el balón no tiene coordenadas en ese momento. Se dibujan los eslabones de la cadena y, si viene, el defensor arrastrado. Nada inventado.
- **Código visual propuesto:**
  - Un punto numerado en el `start` de cada eslabón, con el nombre y el crédito.
  - Una flecha continua de `start` a `end` para cada pase o remate.
  - Solo el punto en la recuperación, porque su `end` es `null`.
  - Una flecha discontinua y de otro color para el desmarque de Torres.
  - Una flecha roja del defensor, de `dragged_defender_start` a `dragged_defender_end`, con la etiqueta «+9.5 m de espacio» (sale de `invisible_assist.space_opened_m`).
  - Una línea punteada para el tramo del balón que no está en la cadena: del último eslabón con balón al `start` del siguiente con balón. El desmarque se salta, porque Torres no toca el balón. En el 1-1, la punteada va de Cota a Salgado, no a Torres.
  - Animar los eslabones en orden de `t_s`.
- **Si no vienen `start` y `end`**, como en órdenes viejas, se muestra la cadena como hoy, sin cancha.

---

## Qué necesita cada quien

### Diego, agentes

Sin este ajuste, las coordenadas entran a los prompts. Eso tiene tres efectos:

- **Se pierde la caché de los dos `goal_chain`.** La clave de caché es el hash del payload, y el payload cambiaría. Habría llamadas nuevas al modelo, los textos de los dos goles podrían cambiar y, con `--offline`, saldrían de plantilla.
- **El modelo ve números que no debe usar,** como `[92, 26]`.
- **El verificador se vuelve más permisivo.** Las coordenadas entran a `allowed_numbers`, y un «92» inventado pasaría solo porque coincide con una coordenada.

Pasos:

1. **Sacar las coordenadas de lo que ven los agentes.** Los campos de dibujo viven *dentro* de cada eslabón de `chain`, y el filtro actual con `UI_ONLY_FACTS` solo quita claves del primer nivel de `facts`. Una forma de hacerlo, en `agents/baja_agents/checks.py`:

   ```python
   # Fields of each goal chain link that only the pitch drawing uses
   CHAIN_DRAWING_KEYS = ("start", "end", "dragged_defender", "dragged_defender_start", "dragged_defender_end")

   def facts_for_agents(facts: dict) -> dict:
       """facts without UI-only fields, also inside each link of the goal chain."""
       out = {k: v for k, v in facts.items() if k not in UI_ONLY_FACTS}
       if isinstance(out.get("chain"), list):
           out["chain"] = [{k: v for k, v in link.items() if k not in CHAIN_DRAWING_KEYS} for link in out["chain"]]
       return out
   ```

   Usarla en lugar de `{k: v for k, v in ...facts.items() if k not in UI_ONLY_FACTS}` en estos lugares:
   - `curator.py`, línea 115.
   - `narrator.py`, líneas 61 y 69.
   - `content()` de `checks.py`, aplicada a `insight["facts"]` antes de `_without_ids`. No conviene agregar estas claves a `EVENT_ID_KEYS`, porque `dragged_defender` también existe en `invisible_assist` y ahí sí se usa.

   Con eso, los payloads quedan **idénticos** a los de antes. Se comprobó quitando esos cinco campos de cada eslabón: `insights.json` queda igual al anterior.
2. **Opcional, en el chat.** En `ask.py`, el `_without_ids` de la línea 117 puede ignorar también `CHAIN_DRAWING_KEYS`. `get_goal_chain` ahora devuelve las coordenadas, y así no cuentan como números permitidos en las respuestas.
3. **Regenerar las órdenes:** `cd agents` y `venv/Scripts/python.exe -m baja_agents run`. Debe reportar puros aciertos de caché, sin llamadas nuevas al modelo.
4. **Comprobar el diff de `data/m001/overlays.json`.** Solo deben cambiar los `chain_detail` de las 8 órdenes `goal_analysis`, con los campos nuevos. Ningún `title` ni `text` debe cambiar. Si alguno cambia, la caché no se reutilizó.
5. **Validar:** `python -m baja_insights validate data/m001/overlays.json`, y correr las pruebas de `agents/tests`.

### luismar, interfaz

1. **Ampliar `ChainLink`** en `web/src/contracts/overlay.ts` con los campos opcionales (hoy solo tiene los de v1):

   ```ts
   export type PitchPoint = [number, number];
   export interface ChainLink {
     event_id: number; player: string; action: string; credit: number; t_s: number;
     type?: string; lines_broken?: number; cross?: boolean;
     start?: PitchPoint | null; end?: PitchPoint | null;
     dragged_defender?: string; dragged_defender_start?: PitchPoint | null; dragged_defender_end?: PitchPoint | null;
   }
   ```
2. **Dibujar la jugada** en `goal_analysis` sobre `PitchBackdrop`, con la conversión `(x · 10, (68 − y) · 10)` y el código visual de arriba. Es más claro en modo analista, que ya usa `chain_detail`.
3. **Textos en `i18n/strings.ts`** para la etiqueta del espacio: «+{m} m de espacio» y «+{m} m of space». El número sale de `invisible_assist.space_opened_m`.
4. **Probar desde ya con el mock:** `mocks/overlays_sample.json`, órdenes `o037` a `o040` para el 1-1 y `o005` a `o008` para el 0-1. Cuando Diego regenere, con `data/m001/overlays.json`.
5. **Comprobar a ojo:** Torres sale de la banda de abajo (y = 10) y entra en diagonal; Cárdenas se va del centro hacia Torres; Ramírez recibe en el hueco y remata hacia la portería de la derecha. Si Torres aparece arriba, falta invertir el eje y.

### Integrante 1, motor y despliegue

1. Subir la rama: `git push -u origin motor/goal-chain-coords`.
2. Abrir el PR contra `motor/mocks-v1.1` si ese PR no se ha integrado, o contra `main` si ya se integró.
3. Después de que se integre el PR de Diego con las órdenes regeneradas, el workflow publica una nueva imagen de `baja-stream`. Desplegarla:

   ```
   az containerapp update -n baja-stream -g rg-baja-insights --image ghcr.io/jesus292005/baja-stream:sha-<commit corto>
   ```

   Hasta ese momento, el modo en vivo sigue mostrando la cadena sin cancha. `baja-chat` también publica una imagen nueva porque cambian `mocks/` y `contracts/`, pero no hace falta desplegarla para el dibujo.

---

## Orden de integración

1. `motor/mocks-v1.1`, si sigue abierto.
2. `motor/goal-chain-coords` (este PR).
3. Diego: ajuste de `facts_for_agents` y `data/m001/overlays.json` regenerado.
4. luismar: dibujo de la jugada. Puede empezar en paralelo con los mocks.
5. Despliegue de `baja-stream`.

## Checklist

- [ ] Visto bueno de Diego a los cambios de `mocks/` y `contracts/`
- [ ] Visto bueno de luismar a los cambios de `mocks/` y `contracts/`
- [ ] Diego: coordenadas fuera de los prompts y del verificador
- [ ] Diego: `overlays.json` regenerado, sin cambios de texto y validado
- [ ] luismar: `ChainLink` ampliado
- [ ] luismar: jugada dibujada en `goal_analysis`, con el eje y invertido
- [ ] `baja-stream` desplegado con las órdenes nuevas
