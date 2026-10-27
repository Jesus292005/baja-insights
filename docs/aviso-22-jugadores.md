# 22 jugadores y balón parado: qué cambió y qué necesita cada quien

Rama `feature/22-jugadores-motor`, del integrante 1, sobre `motor/goal-chain-coords`. Se integra a `feature/22-jugadores`, la rama del equipo para esta parte. `main` no se toca.

| Commit | Qué hace |
| --- | --- |
| `bc7ad2a` | El generador emite balones parados reales. El demo pasa a la semilla 769 |
| `2fa502d` | Posiciones ilustrativas de los 22 jugadores y el balón, el formato y el archivo servido por el stream |

**Toca `contracts/` y `mocks/`, así que necesita el visto bueno de Diego y de luismar** (ver `CONTRIBUTING.md`).

---

## En resumen

- **Balón parado real en los eventos.**
  - Un balón que sale cruza una línea, y el pase termina en ella con `out_of_play`.
  - El rival reanuda con un pase marcado con `set_piece`: `throw_in` desde la banda, `corner` desde el banderín o `goal_kick` desde el área chica.
  - También llevan `set_piece` los saques iniciales, los tiros libres tras falta y el saque del portero tras una atajada (`keeper`).
  - Nadie presiona ni disputa el balón antes de que se cobre.
- **El partido `m001` se regeneró con la semilla 769.** El relleno entre jugadas cambió, así que cambian casi todos los insights y sus `insight_id`. La historia se mantiene (abajo).
- **`data/m001/positions.json`:** los 22 jugadores y el balón a 2 cuadros por segundo, anclados a cada evento.
  - El stream lo sirve en `GET /positions/m001`.
  - Hay una muestra de 60 s del 1-1 en `mocks/positions_sample.json`.
- **Cambio de lado al medio tiempo:** en el segundo tiempo todo se dibuja rotado 180°.

---

## 1. La historia de `m001` con la semilla 769

Se eligió entre unas 1,500 semillas porque es la que mejor conserva la historia. `tests/test_demo_story.py` sigue pasando:

- **Igual:**
  - 1-1, con goles en el 17 y en el 63.
  - La cadena del empate es la misma: Cota, Torres, Salgado y Ramírez, con los mismos créditos y la asistencia invisible de Torres.
  - Torres va primero a las 35:00, sube al primer lugar en el 31 y gana el MVP.
  - Mena pierde el primer tramo del duelo con Verdugo y le da la vuelta en el 20.
  - Cardón controla el primer tiempo y Bahía tiene su presión alta en el segundo (`pressure_shift` de 67 a 77).
  - Veredicto: «Bahía FC generó más peligro aunque tuvo menos la pelota».
- **Cambia:**
  - El **top 3 final ahora es Torres (8.5), Cota (7.9) y Sandoval (7.8)**. Antes el tercero era Rosas. Revisen el guion del video y el pitch si lo mencionan.
  - Hay 71 insights en lugar de 63.

## 2. Posiciones de los 22 jugadores

**Formato:** `contracts/positions.schema.json`, explicado en `contracts/README.md`, sección «Posiciones de los 22 jugadores».

| Campo | Qué es |
| --- | --- |
| `frames[]` | `t` (segundo de partido), `b` (balón), `h` y `a` (11 puntos `[x, y]` por equipo) |
| `teams` | El orden de los 11 de cada equipo, con número y posición |
| `lineup_changes` | Las sustituciones: desde `t_s`, `player_in` toma el lugar de `player_out` |
| `set_pieces` | Cada saque: tipo, equipo, quién saca, desde dónde, cuándo quedó muerto el balón y cuándo se cobra |
| `periods` | El cambio de lado (abajo) |
| `illustrative` | Siempre `true`. En pantalla: «Illustrative positions» |

**Cómo se calculan.** Es un modelo determinista, sin IA ni tokens:

- Cada jugador ocupa la zona de su posición, la misma que usa el generador para elegir quién hace cada acción.
- El bloque sigue al balón, se abre con la pelota y se cierra sin ella.
- La altura de la presión sale de las fases del guion. La línea defensiva de Bahía sin balón pasa de 27.6 m en el primer tiempo a 44.5 m en su presión alta, que es lo que dice el insight `pressure_shift`.
- Cada evento ancla a sus jugadores a su punto y a su segundo:
  - El jugador con balón.
  - El receptor de cada pase.
  - El corredor y el defensor arrastrado. En el 1-1, Torres y Cárdenas llegan juntos al final del desmarque justo cuando Salgado da el pase.
  - El portero en cada atajada.
  - El rival en duelos, presiones, entradas y faltas.
- En cada balón parado los dos equipos toman la forma del saque:
  - **Saque inicial:** cada equipo en su mitad.
  - **Saque de banda:** los rivales a 2 m.
  - **Corner:** cinco atacantes en el área.
  - **Saque de meta:** los centrales abiertos y el rival fuera del área.
  - **Tiro libre:** los rivales a 9.15 m, con barrera de 3 cerca del área.
  - **Saque del portero.**
- Velocidad máxima de 8.5 m/s y 1.5 m de separación mínima.

**Qué tan fiel es** (pruebas en `tests/test_positions.py`):

- El jugador de cada evento está exactamente en su punto, salvo 2 de unos 1,400, a menos de 4 m.
- El balón está en el punto de cada acción.
- El 96% de los receptores está a menos de 2 m del final del pase.
- Solo 47 de 237,000 movimientos superan 9.5 m/s.

**Las posiciones son solo para dibujar.** No entran al motor, a los insights, a los agentes ni al chat. El contrato sigue diciendo que la altura de la línea defensiva y la distancia recorrida no se miden.

## 3. Cambio de lado al medio tiempo

Las coordenadas siguen la convención de los eventos: Bahía ataca hacia x = 105 en los dos tiempos. **En pantalla, en el segundo tiempo (`t ≥ 2700`), todo lo que se dibuja en la cancha va rotado: `(105 − x, 68 − y)`.** Esto incluye jugadores, balón, la cadena del gol y los eventos. Así Bahía ataca a la derecha en el primer tiempo y a la izquierda en el segundo. En el SVG de 1050 × 680, después de rotar, un punto va en `(x · 10, (68 − y) · 10)`.

A las 45:00 los dos equipos aparecen ya en la formación del saque inicial del segundo tiempo, con los lados cambiados.

---

## Qué necesita cada quien

### Diego, agentes

1. **Regenerar `data/m001/overlays.json` con el modelo.** Los insights cambiaron casi todos, así que la caché no sirve. Habrá llamadas nuevas al modelo y textos nuevos. Revisen el presupuesto de 250 llamadas por partido.
2. **Antes de regenerar, el ajuste de `facts_for_agents`** de `aviso-cadena-coordenadas.md`. Así las coordenadas de la cadena del gol no entran a los prompts ni a `allowed_numbers`.
3. **Actualizar `agents/tests/test_agents.py`.** Usa `insight_id` de `m001` que ahora apuntan a otros insights. Equivalencias sugeridas, con números que pueden cambiar:

   | Antes | Era | Ahora |
   | --- | --- | --- |
   | `i44` | `goal_chain` del 1-1 | `i45` |
   | `i35` | `standout_milestone` de Cota | `i49` (Cota defensivo, 65') |
   | `i11` | `team_phase` control de Cardón | `i06` |
   | `i06` | `mvp_rank_change` de Cota | `i05` |
   | `i34` | `match_keys` | `i29` |
   | `i09` | `duel_state` Mena contra Verdugo, 12' | `i04` |
   | `i07` | `card_upgrade` de regate | `i14` (Mena, 26') |
   | `i25` | `mvp_rank_change` | Elegir otro de `data/m001/insights.json` |

4. **Nada que cambiar por las posiciones.** Los agentes no las leen. Si Pregúntale al partido recibe «¿dónde estaba X?», responde solo con eventos y aclara que la cancha es ilustrativa.

### luismar, interfaz

1. **Leer las posiciones:** `GET <stream>/positions/m001` (comprimido, con CORS), o el archivo `data/m001/positions.json` directo.
2. **Elegir el cuadro con el `t_s` del reloj e interpolar entre cuadros a 60 fps.** A 60× los jugadores se ven frenéticos. Conviene que en los momentos clave el reloj vaya a 1× o 2×; la casilla «Speed up only between moments» ya ayuda.
3. **Rotar el segundo tiempo** como dice la sección 3, también para la cadena del gol y para la capa de balón.
4. **Etiqueta «Illustrative positions»** y un interruptor para ocultar a los jugadores.
5. **Mostrar el tipo de saque** si quieren: `set_pieces` trae cada uno con su `t_s` y su lugar.
6. **Probar con `mocks/positions_sample.json`** (62:30 a 63:30). El 1-1 debe verse así: Torres sale de la banda y entra en diagonal, Cárdenas se va del centro tras él, y Ramírez recibe en el hueco.

### Integrante 1

- Subir las ramas: `git push -u origin feature/22-jugadores feature/22-jugadores-motor`.
- Abrir el PR de `feature/22-jugadores-motor` contra `feature/22-jugadores`.
- Para probarlo desplegado sin tocar lo actual: lanzar a mano el workflow de `baja-stream` sobre la rama y desplegar la imagen en otro container app.

---

## Checklist

- [ ] Visto bueno de Diego a `contracts/` y `mocks/`
- [ ] Visto bueno de luismar a `contracts/` y `mocks/`
- [ ] Diego: `facts_for_agents`, `overlays.json` regenerado y pruebas actualizadas
- [ ] luismar: 22 jugadores y balón sobre `PitchBackdrop`, con la rotación del segundo tiempo y la etiqueta
- [ ] Revisar el guion del video y el pitch por el nuevo top 3
- [ ] Probar desplegado en un container app aparte antes de decidir si va a `main`
