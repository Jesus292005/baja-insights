# Nueva versión del generador y el motor: guía para el equipo

Rama `motor-realism`, del integrante 1. Explica qué cambió, qué no cambió y qué tiene que hacer cada quien para que todo funcione.

**Resumen en cuatro líneas**
1. Los partidos sintéticos ahora se parecen al fútbol real, el MVP está equilibrado y las cartas usan los 7 atributos.
2. El partido de demo `m001` se regeneró (semilla 44), con la misma historia en lo esencial.
3. Los eslabones de la cadena del gol traen el tipo de acción, así que la interfaz puede mostrarla en cualquier idioma.
4. El motivo de cada carta trae un código y sus números (opción A, acordada por los tres), con el mismo fin.

---

## 1. Qué cambió

### Generador: partidos más realistas

Medido contra promedios aproximados de la Premier League con `python -m baja_insights realism`. Antes, 9 de 14 métricas estaban fuera de rango; ahora todas están dentro.

| Por equipo y partido | Antes | Ahora | Premier League aprox. |
| --- | --- | --- | --- |
| Goles por partido | 1.1 | 2.9 | 2.2 a 3.4 |
| Tiros | 6.8 | 11.3 | 9 a 16 |
| xG | 0.58 | 1.47 | 1.0 a 1.8 |
| Entradas | 0 | 15 | 10 a 22 |
| Faltas | 5.7 | 10.5 | 8 a 14 |
| Acciones del portero | 9 | 24 | 20 a 50 |
| Titulares | Bahía jugaba con 10 | 11 | 11 |

### Motor: MVP equilibrado y cartas completas

- **MVP.** Antes ningún defensa quedaba primero. Las referencias por rol no correspondían al generador y se recalcularon. Ahora el MVP es un atacante la mitad de las veces, un mediocampista el 42% y un defensa el 8%.
- **Cartas.** Antes Ritmo y Regate no subían nunca y el 70% de las subidas eran de Defensa. Ahora suben los 7 atributos, con reglas nuevas para Ritmo (desmarque a 30 km/h o más), Regate (2 regates en 10 minutos) y Sin balón (+1 cuando el desmarque termina en remate). Cada motivo de carta trae una cifra como máximo, que es lo que permiten los textos para aficionados.
- **Duelos.** Un aviso cada 5 minutos como mínimo, y un cambio de signo solo cuenta si la barra queda a 0.10 o más del cero.

### Cadena del gol en cualquier idioma (propuesta del integrante 2)

Cada eslabón de `goal_chain.facts.chain` trae tres campos nuevos, copiados del evento. `action` se queda igual, en español, para no romper nada.

| Campo | Qué es | Ejemplo |
| --- | --- | --- |
| `type` | El tipo del evento, el mismo vocabulario de `event.schema.json` | `pass`, `recovery`, `shot`, `off_ball_run`, `tackle` |
| `lines_broken` | Líneas rotas por el pase, 0 si no aplica | `2` |
| `cross` | Solo aparece, en `true`, si el pase es un centro | `true` |

```json
{"event_id": 1355, "player": "R. Salgado", "action": "pase que rompió 2 líneas", "credit": 0.35, "t_s": 3787,
 "type": "pass", "lines_broken": 2}
```

Son opcionales en `insight.schema.json` y en `chain_link` de `overlay.schema.json`. También los devuelve `get_goal_chain`. Ya hay ejemplos en `mocks/insights_sample.json` (`i02` con un centro, `i11` con el desmarque) y en `mocks/chat_tools_sample.json`. **Como toca `contracts/`, el PR necesita el visto bueno de los tres.**

### Motivo de la carta en cualquier idioma (opción A)

Cada cambio de carta (`card_change` dentro de `mvp_rank_change` y `standout_milestone`, y los facts de `card_upgrade`) trae dos campos nuevos. `reason` se queda igual, en español.

| Campo | Qué es |
| --- | --- |
| `reason_code` | Qué dice el motivo, uno de 10 códigos |
| `reason_params` | Los números y nombres del motivo, según el código |

```json
{"attribute": "defensa", "from": 58, "to": 60, "delta": 2,
 "reason": "tercera recuperación en campo rival en menos de 10 minutos",
 "reason_code": "opp_half_recoveries", "reason_params": {"count": 3, "window_min": 10},
 "overall_from": 70, "overall_to": 70}
```

Son opcionales en `card_change` de `insight.schema.json` y en `card` de `overlay.schema.json`. La tabla completa de códigos está en la sección 5 y en `contracts/README.md`. También los devuelve `get_player_summary` en `card_changes`. Ya hay ejemplos en `mocks/insights_sample.json` y en `mocks/chat_tools_sample.json`.

### Datos de prueba que cambiaron

- `mocks/teams.json`: O. Félix (MC, Bahía FC) ahora es **titular**, y cambiaron los valores de `role_baselines_per_90`.
- `mocks/insights_sample.json` y `mocks/chat_tools_sample.json`: solo se agregaron los campos nuevos de la cadena y de la carta. Nada más cambia en los mocks.
- `data/m001` y `data/free-seed2`: eventos e insights regenerados.

---

## 2. Qué no cambió

- **El contrato**, salvo los campos opcionales de la cadena (`type`, `lines_broken`, `cross`) y de la carta (`reason_code`, `reason_params`). Nada que ya exista deja de validar.
- **El servicio de stream** y sus mensajes.
- **Las funciones del chat.** Solo cambian las cifras de `m001`; la forma de las respuestas es la misma, más los campos de la cadena.
- **La historia del demo, en lo esencial.** Se mantienen:
  - el 1-1 en el 17 y en el 63;
  - la cadena del empate con la asistencia invisible de Torres;
  - Torres primero a las 35:00 y al final;
  - el veredicto «Bahía FC generó más peligro aunque tuvo menos la pelota».

  `tests/test_demo_story.py` lo protege.

---

## 3. La historia del demo, minuto a minuto

| Momento | Qué pasa |
| --- | --- |
| 11:09 | Cota sube al 1.º del MVP |
| 14:10 | Torres sube al 2.º |
| 15:00 | Fase de control de Real Cardón |
| 17:40 | Gol 0-1 de Leyva |
| 19:00 a 40:00 | Torres lidera la carrera MVP (en `data.ranking` de cada `mvp_update`) |
| 43:00 a 68:00 | Cota lidera |
| 45:00 | Claves del medio tiempo |
| 63:09 | Gol 1-1 de Ramírez, con la asistencia invisible de Torres |
| 77:00 | Fase de presión de Bahía (antes no salía) |
| 79:06 | Torres sube al 1.º y termina empatado con Cota en 8.2 |
| 90:00 | Top 3: Torres, Cota y Salgado (el mock dice Torres, Cota y Rosas) |

**Para el guion del video:** no hay un aviso «Torres sube al primer lugar» antes de las 35:00. Torres llega ahí cuando Cota baja, y esos cambios no se anuncian. Para «¿Por qué Torres va primero?» conviene mostrar la carrera MVP, donde sí aparece primero.

---

## 4. Integrante 2, agentes (Diego)

**Código: un solo cambio, de una línea.** `data_for` ya copia el eslabón completo a `chain_detail`, así que los campos de la cadena llegan solos. Los de la carta no: `card_for` copia los campos uno por uno. Se probó en local, sin tocar tus archivos y con tu `checks.py` de `main` (después del PR #7): tus plantillas pasan `check_variant` con los 63 insights nuevos de `m001` y los 15 del mock, y tus 100 tests pasan con las equivalencias de la tabla de abajo.

**Lo que tienes que hacer:**

- [ ] **Copiar `reason_code` y `reason_params` en `card_for`** (`agents/baja_agents/overlays.py`), junto a `reason`:

  ```python
  "overall_from": change["overall_from"], "overall_to": change["overall_to"], "reason": change["reason"],
  **{k: change[k] for k in ("reason_code", "reason_params") if k in change}}
  ```

  Solo se copian si vienen, así que sigue funcionando con insights viejos. No uses `change.get("reason_code")`: con un insight viejo pondría `null` y la orden ya no cumpliría el esquema, porque `reason_code` es un `enum`. Con este cambio, las 500 órdenes de prueba (insights nuevos, viejos y del mock) cumplen `overlay.schema.json`. Puedes extender `test_v11_fields_are_copied_from_the_insight` para que los revise.
- [ ] **Regenerar `data/m001/overlays.json` y `agents_report.json`** con `python -m baja_agents run`, una sola vez, después del merge. Ya lo hiciste en el PR #7 (`4a10aae`), pero esas órdenes salieron de los insights de antes y apuntan a insights que ya cambiaron. Esta vez la caché no sirve para los insights nuevos, así que sí habrá llamadas al modelo.
- [ ] **Actualizar los tests que buscan insights de `m001` por identificador.** Mientras no se actualicen, el job `agents` de la CI va a fallar. Las equivalencias se comprobaron con las mismas aserciones de tus tests y con `checks.py` tal como está en `main`:

| Antes | Ahora | Qué es | Cambia en el test |
| --- | --- | --- | --- |
| `i01` | `i09` | Duelo de Mena contra Verdugo (12:25), sin cambio de signo, prioridad 0.45 | Solo el identificador. El `i01` nuevo tiene prioridad 0.37, menos que `MIN_PRIORITY`, así que el curador lo descarta por «prioridad baja» y no por «repetido» |
| `i03` | `i06` | Sube en el MVP con ranking (Cota, 2.7) | «Cota sube con 2.7 puntos» pasa y «Cota sube con 2.6 puntos» se marca (el 2.6 es de otro jugador del ranking), en vez de Montaño con 2.3 y 2.7 |
| `i02` | `i11` | Control de Real Cardón | «62% de posesión entre 05:00-15:00» en vez de «64%… 01:00-11:00» |
| `i07` | `i07` | Carta (ahora de Regate de Cota) | Nada, solo valida el esquema |
| `i22` | `i25` | MVP mientras va 0-1 (Leyva, minuto 30) | El nombre del texto: Leyva en vez de Montaño |
| `i26` | `i34` | Claves del medio tiempo | Posesión `{"Bahía FC": 43, "Real Cardón": 57}`; D. Mena ya no aparece, usar J. Torres o B. Haro en `who_is_who`. En el test del ranking: «Bahía FC suma 15 recuperaciones en mitad rival, 7 de Torres» en vez de 21 y 9 |
| `i38` | `i44` | Gol del 1-1 con la asistencia invisible de Torres | Solo el identificador |
| `i46` | `i35` | Hito de Cota, minuto 45 | 10 recuperaciones y 4 pases progresivos en vez de 12 y 16; el caso del pase clave mal etiquetado queda «4 pases clave» |

**Opcional:**
- [ ] Usar `type` y `lines_broken` cuando el Narrador cuenta la cadena en inglés, en lugar de traducir `action`.
- [ ] Sigue pendiente lo que ya estaba en `docs/estado-motor-v1.1.md`: el endpoint `POST /api/ask`. Lo de `allowed_numbers` y el ranking ya quedó resuelto en tu PR #7.

El test del curador que no ve el ranking (bloque 10:00-15:00) no necesita cambios.

---

## 5. Integrante 3, interfaz (luismar)

**Código: nada es obligatorio para que siga funcionando.** Todos los campos nuevos son opcionales.

**Para que funcione perfecto:**

- [ ] **Agregar los campos a `ChainLink`** en `web/src/contracts/overlay.ts`:

  ```ts
  export interface ChainLink {
    event_id: number; player: string; action: string; credit: number; t_s: number;
    type?: 'pass' | 'shot' | 'tackle' | 'recovery' | 'duel' | 'pressure' | 'foul' | 'off_ball_run';
    lines_broken?: number;
    cross?: boolean;
  }
  ```

- [ ] **Armar la etiqueta en cada idioma** en `web/src/i18n/strings.ts`, con `action` como respaldo si falta `type`. Estas son las mismas reglas que usa el motor para la etiqueta en español:

| `type` y campos | Español (igual que `action`) | Inglés sugerido |
| --- | --- | --- |
| `recovery` | recuperación | recovery |
| `tackle` | entrada ganada | tackle won |
| `shot` | remate | shot |
| `off_ball_run` | desmarque y arrastre de marca | off-ball run that dragged a marker |
| `pass` con `cross` | centro | cross |
| `pass` con `lines_broken` ≥ 2 | pase que rompió N líneas | pass that broke N lines |
| `pass` con `lines_broken` = 1 | pase que rompió 1 línea | pass that broke 1 line |
| `pass` sin líneas | pase | pass |

- [ ] **Agregar los campos a la carta** en `web/src/contracts/overlay.ts`, junto a `reason`:

  ```ts
  reason_code?: 'line_breaking_pass' | 'opp_half_recoveries' | 'shot_speed' | 'duel_streak' | 'run_speed'
    | 'dribbles' | 'run_ended_in_shot' | 'run_opened_goal' | 'standout_defensive' | 'standout_creative';
  reason_params?: Record<string, number | string | boolean | null>;
  ```

- [ ] **Escribir el motivo de la carta en cada idioma** en `web/src/i18n/strings.ts`, con `reason` como respaldo si falta `reason_code`. El español puede ser el mismo texto de `reason`:

| `reason_code` | `reason_params` | Inglés sugerido |
| --- | --- | --- |
| `line_breaking_pass` | `lines`, `under_pressure` | pass that broke {lines} lines (under pressure) |
| `opp_half_recoveries` | `count`, `window_min` | {count} recoveries in the opposition half in under {window_min} minutes |
| `shot_speed` | `speed_kmh` | shot at {speed_kmh} km/h |
| `duel_streak` | `count` | {count} duels won in a row |
| `run_speed` | `speed_kmh` | run at {speed_kmh} km/h |
| `dribbles` | `count`, `window_min` | {count} dribbles in under {window_min} minutes |
| `run_ended_in_shot` | `dragged_defender` | dragged {dragged_defender} and the move ended in a shot |
| `run_opened_goal` | `dragged_defender`, `dragged_position` | dragged {dragged_defender} and opened the space for the goal |
| `standout_defensive` | ninguno | defensive game above what the role expects |
| `standout_creative` | ninguno | creative game above what the role expects |

  En modo aficionado cuida que el texto lleve una cifra como máximo, igual que los textos de los agentes: por ejemplo, el número con letra en `dribbles`.
- [ ] **Revisar las cartas de Ritmo, Regate y Sin balón**, que antes nunca salían.
- [ ] **Alineaciones:** si la interfaz las muestra, ahora aparece O. Félix como titular de Bahía FC.
- [ ] **Grabar el video con las órdenes que regenere Diego**, no con las actuales.

---

## 6. `card.reason`: decidido, opción A

Los tres eligieron que el motor mande un código. Ya está hecho en esta rama (sección 1). Lo que queda: Diego copia los dos campos en `card_for` y luismar escribe los textos por código (secciones 4 y 5).

---

## 7. Orden sugerido

1. Los tres revisan el PR de `motor-realism`, porque toca `contracts/`.
2. Merge. El job `test` de la CI pasa; el job `agents` falla en los tests de la tabla de arriba hasta que Diego los actualice.
3. Diego actualiza sus tests y regenera las órdenes, idealmente el mismo día del merge.
   - **No actualizar `baja-stream` en Azure antes de eso.** El servicio está fijo en la imagen `sha-c81b433` (ver `docs/despliegue.md`). El merge publica una imagen nueva en GHCR, pero no la despliega. Si se despliega antes de regenerar las órdenes, el partido nuevo sale con los gráficos del partido viejo. El orden es: merge, órdenes regeneradas en `main`, y después `az containerapp update` con el `sha` de ese commit.
   - **Hecho el 24 de octubre:** `baja-stream` corre `sha-7048698`, el merge del PR #12 con las órdenes regeneradas.
4. Luismar agrega los campos nuevos a los tipos y los textos por idioma.
5. Datos congelados: nadie cambia `m001` hasta después de grabar el video.
