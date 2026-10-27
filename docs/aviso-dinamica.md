# Juego vivo: qué cambió en los datos y qué necesita cada quien

Rama `feature/22-jugadores-dinamica-motor`, del integrante 1, contra **`feature/22-jugadores-dinamica`**. Es la parte del integrante 1 de `plan-dinamica-juego.md` (G1 a G5 y P1 a P5).

| Commit | Qué hace |
| --- | --- |
| `d30b416` | Generador: conducción, desmarques que terminan en pase, saques más ágiles y guion relajado |
| `600646b` | Posiciones: presión al que conduce, marca en los desmarques, apoyos y separación entre compañeros |

Los checks de `agents` y `web` van a salir en rojo hasta que Diego regenere las órdenes, como en los PR anteriores: las órdenes actuales citan eventos e insights del partido anterior.

---

## Metas del plan

| Medida | Antes | Ahora | Meta |
| --- | --- | --- | --- |
| Distancia que conduce el que recibe, sin presión | 0 m siempre | **5.7 m** de mediana | 3 m o más ✔ |
| Desmarques que terminan en pase al que corrió | 2 de 10 | **13 de 17** | 60% o más ✔ |
| Desmarques con defensor que los sigue | Solo el guionizado | Todos los que arrastran a alguien, y los demás con el defensor libre más cercano | ✔ |
| Rival más cercano al que conduce | 7 m | **3.1 m** de mediana | 3 a 5 m ✔ |
| Compañeros encimados (menos de 3.6 m por 2 s o más, fuera de saques) | 85 | **1** | 10 o menos ✔ |
| Espera en los saques de banda | 11.6 s | **unos 5 a 6 s** | Unos 6 s ✔ |
| Distancia por jugador de campo en 90 minutos | 10.5 km | **11.6 km** | 10 a 11.5 km (casi). En la Premier, los mediocampistas corren 12 a 13 |
| Métricas de realismo (partidos libres) | En rango | En rango | ✔ |
| Goles en el 17 y el 63 y cadena del 1-1 | Sí | Sí | ✔ |
| Jugador de cada evento en su punto y balón al pie | Sí | Sí | ✔ |

Los remates se recalibraron porque con la conducción los equipos llegan más al área. Los partidos libres quedan en unos 3 goles y 13 remates por partido.

## Qué cambió en los datos

- **Eventos:** el `start` de una acción puede no coincidir con el `end` del pase que recibió el jugador; la diferencia es lo que condujo. No hay tipo de evento nuevo. Los desmarques con defensor arrastrado siempre traen `dragged_defender_start` y `dragged_defender_end`.
- **El partido `m001` cambió.** Siguen igual los goles en el 17 y el 63 y la cadena del 1-1 (`i52`; el 0-1 es `i15`). Lo demás sale de la semilla:
  - **MVP:** Rosas (8.8), seguido de Torres (8.3) y Cota (8.2).
  - **Primer lugar:** Rosas llega en el minuto 50.
  - **Veredicto:** se mantiene: «Bahía FC generó más peligro aunque tuvo menos la pelota».
- **80 insights.** El formato de `positions.json` no cambia.

---

## Qué necesita cada quien

### Diego, agentes

1. **Regenerar `data/m001/overlays.json`** en una rama sacada de `feature/22-jugadores-dinamica`, una vez que entre este PR.
2. **Quitar del chat lo que asume que Torres va primero.** Con este partido, **Torres no va primero a los 35** y el MVP es Rosas. Revisa los ejemplos, los prompts y las pruebas de Pregúntale al partido.
3. **Revisar el presupuesto de llamadas** (hoy son 187 de 250).

### luismar, interfaz

1. **Cambiar la pregunta sugerida** «Why is Torres first?» / «¿Por qué Torres va primero?» por una que funcione con cualquier partido, como «Who leads the MVP race?» / «¿Quién lidera la carrera al MVP?». **Con estos datos la pregunta actual ya no tiene sentido.**
2. **La opción de 2×** y **pasar rápido el balón parado** con `set_pieces` (plan, L1 y L2).
3. **Revisar las pruebas que dependen de los datos de `m001`** cuando Diego regenere las órdenes.

### Integrante 1

- Subir la rama y abrir el PR contra `feature/22-jugadores-dinamica`.
- Revisar en la web, a 2×:
  - un desmarque largo, por ejemplo el de Rosas en el 21:38, con Cota detrás;
  - juego abierto con presión, por ejemplo del 10:00 al 10:40;
  - un saque de banda;
  - el 1-1;
  - el medio tiempo.

---

## Pendiente para después

- Los contragolpes siguen siendo raros, porque el generador no acelera el juego tras recuperar en campo propio.
- Los eventos tienen resolución de un segundo: si dos acciones caen en el mismo segundo en puntos distintos, el balón salta entre ellas.
