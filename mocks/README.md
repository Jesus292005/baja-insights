# Datos de ejemplo de Baja-Insights

Estos archivos sirven para que cada integrante avance **sin esperar a los demás**. Son datos escritos a mano que respetan los contratos acordados. Cuando el motor real esté listo, solo se cambia la fuente de datos.

El partido de ejemplo es **Bahía FC 1-1 Real Cardón**. Equipos, jugadores y estadio son ficticios.

**La historia del partido**
- Cardón controla el primer tiempo y anota en el 17 con un pase de Rosas que rompe dos líneas.
- Torres recupera tres balones en campo rival entre el 24 y el 33 y sube al primer lugar del MVP.
- Cota, el medio de contención, hace un partidazo que normalmente nadie notaría.
- Mena pierde el primer duelo contra Verdugo y luego le da la vuelta.
- Bahía sube la presión en el segundo tiempo y empata en el 63. El gol es de Ramírez, pero nace de una recuperación de Cota y de un desmarque de Torres que arrastra al central sin tocar el balón.
- Top 3 final con Torres, Cota y Rosas.

---

## Archivos

| Archivo | Qué contiene | Quién lo usa |
| --- | --- | --- |
| **teams.json** | Datos del partido, convenciones de campo, plantillas con atributos base de carta y valores esperados por rol | Los tres |
| **events_sample.json** | Extracto de 50 eventos con las jugadas clave del partido | Integrante 1 como referencia del formato |
| **events_sample.jsonl** | Los mismos eventos, uno por línea, para simular el streaming | Integrante 1 |
| **insights_sample.json** | 15 insights como los que producirá el motor | Integrante 2 para construir los agentes |
| **overlays_sample.json** | 53 órdenes de gráfico en cuatro variantes, aficionado y analista en español e inglés | Integrante 3 para construir la interfaz |
| **chat_tools_sample.json** | Funciones de consulta para Pregúntale al partido y 5 conversaciones de ejemplo | Integrante 2 y el chat de la interfaz |

---

## Cómo usarlos

**Integrante 1, motor.** Su meta es que el generador y el motor produzcan archivos con exactamente esta forma. Los insights de ejemplo sirven como prueba. Si el motor recibe estos eventos, debería producir algo parecido a estos insights.

**Integrante 2, agentes.** Cargar `insights_sample.json` y mandarlos uno por uno al curador como si llegaran en vivo. La salida de los agentes debe tener la forma de `overlays_sample.json`. Para el chat, implementar las funciones de `chat_tools_sample.json` leyendo los archivos de ejemplo y usar las conversaciones como casos de prueba.

**Integrante 3, interfaz.** Reproducir `overlays_sample.json` con un reloj simulado. Mostrar cada orden cuando `show_at_s` coincide con el reloj, filtrando por el `mode` y el `language` elegidos. Las órdenes con `mode` y `language` en `all` se muestran siempre. Con esto se puede construir la interfaz completa, incluido el cambio de modo e idioma.

---

## Convenciones

- **Campo** de 105 por 68 metros, con el origen en la esquina inferior izquierda.
- **Bahía FC ataca siempre hacia x=105** y Real Cardón hacia x=0, en los dos tiempos, para simplificar.
- **Reloj continuo** sin tiempo agregado. El segundo tiempo empieza en 45:00 con `period` igual a 2.
- **Posiciones** en español, POR, LD, LI, DFC, MCD, MC, ED, EI y DC.
- **Atributos de carta** ritmo, disparo, vision, regate, defensa, fisico y sin_balon.
- Los IDs de evento del extracto no son consecutivos porque es un fragmento de un partido de unos 2,000 eventos.
- Los números de los insights resumen el partido completo simulado, así que algunos incluyen eventos que no están en el extracto.

---

## Cambios a los esquemas que hay que aprobar hoy

Para construir estos ejemplos hizo falta agregar algunos campos. Revísenlos juntos y, si están de acuerdo, quedan como contrato.

**Evento de entrada.** Campos nuevos respecto a la propuesta.

| Campo | Para qué | Tipos de evento |
| --- | --- | --- |
| **period** | Primer o segundo tiempo | Todos |
| **receiver** | A quién iba el pase, para reconstruir la cadena del gol | pass |
| **opponent** | Rival directo, para los duelos | duel, tackle |
| **target** | A quién se presionó | pressure |
| **xg** | Goles esperados del tiro | shot |
| **cross** | Si el pase fue centro | pass |
| **assist** y **score** | Asistencia y marcador después del gol | goal, half_time, match_end |
| **dragged_defender** y **space_opened_m** | Para la asistencia invisible | off_ball_run |
| **fouled** | Quién recibió la falta | foul |
| **player_in** y **player_out** | Cambios | substitution |

Tipos de evento nuevos `recovery`, `duel`, `off_ball_run` y `second_half_start`.

**Insight del motor.** Este esquema no estaba en la propuesta y es el contrato entre los integrantes 1 y 2.

```json
{
  "insight_id": "i05",
  "match_id": "m001",
  "period": 1,
  "minute": 33,
  "second": 40,
  "type": "mvp_rank_change",
  "priority": 0.85,
  "players": ["J. Torres"],
  "team": "Bahía FC",
  "facts": { "from_rank": 3, "to_rank": 1, "score": 6.2, "recoveries": 3 },
  "evidence": [531, 642, 739]
}
```

- **type** puede ser `mvp_rank_change`, `duel_state`, `standout_milestone`, `card_upgrade`, `goal_chain`, `team_phase`, `match_keys`, `top3` o `match_summary`.
- **priority** va de 0 a 1 y la calcula el motor. El curador la usa para decidir qué mostrar.
- **facts** cambia según el tipo. Ver los ejemplos del archivo.
- **evidence** son los `event_id` que respaldan el insight. Así el narrador y el chat pueden citar jugadas reales.

**Orden de gráfico.** Campos nuevos respecto a la propuesta.

| Campo | Para qué |
| --- | --- |
| **overlay_id** | Identificador único |
| **source_insight** | De qué insight salió, o `null` para las animaciones de la barra de duelo |
| **show_at_s** | Segundo del partido en número, más fácil de ordenar que `show_at` |
| **period** | Primer o segundo tiempo |

Valores de **slot** `top_right`, `lower_third`, `side_panel`, `bottom_bar`, `center` y `full_screen`.

Valores de **type** `mvp_update`, `duel_bar`, `standout_milestone`, `card_upgrade`, `goal_analysis`, `team_phase`, `match_keys`, `top3` y `chat_answer`.
