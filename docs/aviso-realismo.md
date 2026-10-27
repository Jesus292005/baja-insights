# Más realismo y más momentos: qué cambió y qué necesita cada quien

Rama `feature/22-jugadores-realismo`, del integrante 1, sacada de `feature/22-jugadores` después del PR #44. Va contra `feature/22-jugadores`. `main` no se toca.

| Commit | Qué hace |
| --- | --- |
| `473f3d0` | Generador: sin robos que nadie provoca, más saques reales. El demo pasa a la semilla 1387 |
| `1c3a96e` | Motor: posesiones largas, rachas de pases, contragolpes y atajadas |
| `9131c24` | Posiciones: el balón va al pie de quien lo lleva, y nadie se mueve hacia una jugada que todavía no puede leer |

**Toca `contracts/` y `mocks/`, así que necesita el visto bueno de Diego y de luismar.** Los checks de `agents` y `web` van a salir en rojo hasta que Diego regenere las órdenes. Es lo mismo que pasó con el PR #41: las órdenes actuales citan eventos e insights del partido anterior.

---

## Por qué

Al ver a los 22 jugadores todo el partido se notaban cosas que antes estaban escondidas:

- Posesiones largas que terminaban en robos sin presión ni pase errado.
- Balón y jugadores que se separaban y luego se juntaban.
- Jugadores que caminaban hacia un pase que nadie había dado.
- Solo el 8% del partido tenía un gráfico en pantalla, con huecos de hasta 7 minutos.

## 1. Generador

- **Sin robos fantasma.** Una posesión muy larga ya no termina con el rival «recuperando» después de un pase bueno. Cerca del área termina en remate. En otra zona, el rival presiona y la gana con una entrada.
- **Cada pérdida queda registrada.** Si el rival recoge un balón suelto, ahora es una recuperación, así que el motor ve todas las pérdidas.
- **Más saques, más cerca de la Premier League.** Un pase errado sale por la línea si termina a 28 m de ella o menos; antes eran 15 m. Por equipo y por partido quedan unos 25 saques de banda y 5 corners, contra 12 y 2 antes. Todas las métricas siguen en el rango de la prueba de realismo.
- **Saques que no se pierden.** Un saque pendiente se cobra aunque antes haya una sustitución. Un tiro libre se cobra antes de la siguiente jugada del guion, así que esas jugadas mantienen su segundo exacto.

### La historia de `m001`, ahora con la semilla 1387

Primero se intentó conservar la 769 ajustando el guion. Volvía todo menos un punto: la carrera del MVP en pantalla no tenía a Torres arriba antes del minuto 35. En el guion (`scripts/m001.json`), Torres ahora presiona y recupera más desde el minuto 15, Cota disputa y recupera más, y Cardón es menos directo en el segundo tiempo. Con ese guion, la 1387 es la que mejor cumple toda la historia entre unas 1,600 semillas.

- **Igual que antes:**
  - 1-1, con goles en el 17 y en el 63, y la misma cadena del empate con la asistencia invisible de Torres.
  - Torres va primero a las 35:00 y gana el MVP.
  - Mena pierde el primer tramo del duelo con Verdugo y le da la vuelta.
  - Cardón tiene control en el primer tiempo y Bahía su presión alta en el segundo.
  - Veredicto: «Bahía FC generó más peligro aunque tuvo menos la pelota».
- **Cambia:**
  - Top 3: **Torres (8.7), Cota (8.5) y Salgado (8.4)**, un final muy cerrado.
  - Torres arriba desde el minuto 33.
  - Mena voltea el duelo desde el 27.
  - Revisen el guion del video y el pitch.

## 2. Motor: momentos que no se contaban

Todos usan tipos de insight que ya existen y salen **después** de los eventos que citan:

| Insight | Cuándo | En `m001` |
| --- | --- | --- |
| `team_phase` con `label: "possession_spell"` | Una sola posesión de 12 pases completados o más. Trae `passes`, `duration_s`, `players_involved` y `ended_in` (`goal`, `shot`, `out`, `foul` o `lost`). Sus `evidence` son los pases. Una por equipo cada 6 minutos | 7, sobre todo de Cardón |
| `card_upgrade`, `reason_code: "pass_streak"` | Cada 20 pases completados seguidos de un jugador de campo. Visión +1. `reason_params: {count}` | 2 (Haro y Meza) |
| `card_upgrade`, `reason_code: "recovery_to_shot"` | Recupera en campo propio y su equipo remata de 3 a 20 s después. Físico +1. `reason_params: {seconds, shooter}` | 1 |
| `card_upgrade`, `reason_code: "big_save"` | El portero ataja un remate de xG 0.15 o más. Defensa +1, o +2 desde xG 0.30. `reason_params: {xg, shooter}` | 4. Antes los porteros no tenían ningún insight |

`m001` pasa de 68 a 82 insights. El formato está en `contracts/README.md`, y los esquemas ya aceptan los códigos y la etiqueta nuevos.

## 3. Posiciones

| | Antes | Ahora |
| --- | --- | --- |
| Distancia entre el balón y quien lo conduce | Hasta 19 m | 0.7 m como máximo |
| Cuánto se acerca el receptor a un pase que todavía no se da | Hasta 6 s antes | Desde 1.5 s antes como máximo |
| Tiempo en que los jugadores están casi quietos | 31% | 16%, porque ahora se reacomodan suavemente alrededor de su lugar |

Lo demás sigue igual: el formato de `positions.json`, los saques, el cambio de lado al medio tiempo y el endpoint `/positions/m001`.

---

## Qué necesita cada quien

### Diego, agentes

1. **Texto en inglés de los tres códigos nuevos,** en `card_reason_en` de `agents/baja_agents/fallback.py`:

   ```python
   if code == "pass_streak":
       return f"{p['count']} passes in a row without a miss"
   if code == "recovery_to_shot":
       return f"won the ball in his own half and the team shot {p['seconds']} seconds later"
   if code == "big_save":
       return f"save from a shot worth {p['xg']:.2f} xG"
   ```

2. **La etiqueta nueva en `_phase`.** Hoy, cualquier etiqueta que no sea `control` cae en el texto de `pressure_shift`. Por ejemplo:

   ```python
   if f["label"] == "possession_spell":
       n, secs = f["passes"], f["duration_s"]
       return {
           "fan_es": (f"{team} la mueve", f"{team} encadenó {n} pases seguidos."),
           "analyst_es": ("Posesión larga", f"{team}: {n} pases en {secs} s, con {f['players_involved']} jugadores."),
           "fan_en": (f"{team} keeps it", f"{team} strung {n} passes together."),
           "analyst_en": ("Long spell", f"{team}: {n} passes in {secs} s, {f['players_involved']} players involved."),
       }
   ```

3. **Regenerar `data/m001/overlays.json`** en una rama tuya sacada de esta. Ojo con el presupuesto: hoy son 187 de 250 llamadas para 45 gráficos. Con más candidatos el curador sigue mostrando como mucho 3 por bloque, pero puede acercarse al límite.
4. **Pruebas que buscan insights por número:** se vuelven a mover, porque los números son consecutivos. Ahora el 1-1 es `i57` y el 0-1 es `i16`. Para que no se rompan otra vez, mejor que las pruebas busquen por tipo y contenido; por ejemplo, el `goal_chain` cuyo `scoreline` es 1-1.

### luismar, interfaz

1. **Agregar la etiqueta `possession_spell`:**
   - En `web/src/contracts/overlay.ts`: `'control' | 'pressure_shift' | 'possession_spell'`.
   - En `web/src/i18n/strings.ts`, en `phase`: `possession_spell: 'Posesión larga'` y `'Long spell'`.
2. **Revisar cómo se dibujan sus pases.** La capa de la jugada dibuja los eventos citados, y una posesión larga cita 12 a 17 pases: queda como un mapa de pases. Si se ve cargado, dibujar solo los últimos 6.
3. **Revisar las pruebas que dependen de los datos de `m001`** (`play.test.ts`, `positions.data.test.ts`) una vez que Diego regenere las órdenes.

---

## Checklist

- [ ] Visto bueno de Diego y de luismar a `contracts/` y `mocks/`
- [ ] Diego: textos de los códigos y la etiqueta, `overlays.json` regenerado y pruebas por tipo
- [ ] luismar: etiqueta `possession_spell` en tipos y textos
- [ ] Revisar en la web: el 1-1, una posesión larga de Cardón (minuto 1 o 21), una atajada de Zamora (64') y el medio tiempo
- [ ] Guion del video y pitch con el nuevo top 3
