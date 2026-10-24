# Generador y motor más realistas: qué cambia para cada uno

Rama `motor-realism`, del integrante 1. **No cambia el contrato**: los esquemas, los campos y los tipos son los mismos. Lo que cambia son los **datos**: los eventos y los insights de `m001`, y algunos valores de `mocks/teams.json`.

---

## Por qué

Los partidos sintéticos no se parecían lo suficiente al fútbol real, y el demo estaba ajustado a una sola historia. Medidos contra promedios aproximados de la Premier League, 9 de 14 métricas estaban fuera de rango:

| Por equipo y partido | Antes | Ahora | Premier League aprox. |
| --- | --- | --- | --- |
| Goles por partido | 1.1 | 2.9 | 2.2 a 3.4 |
| Tiros | 6.8 | 11.3 | 9 a 16 |
| xG | 0.58 | 1.47 | 1.0 a 1.8 |
| Entradas | 0 | 15 | 10 a 22 |
| Faltas | 5.7 | 10.5 | 8 a 14 |
| Acciones del portero | 9 | 24 | 20 a 50 |
| Titulares | Bahía jugaba con 10 | 11 | 11 |

Ahora todas están dentro de rango. Además:

- **MVP más equilibrado.** Antes ningún defensa quedaba primero. Ahora gana un atacante la mitad de las veces, un mediocampista el 42% y un defensa el 8%. Las referencias por rol no correspondían al generador; se recalcularon.
- **Cartas.** Antes Ritmo y Regate no subían nunca, y el 70% de las subidas eran de Defensa. Ahora suben los 7 atributos, y Defensa es el 37%.

Todo queda protegido por tests: `tests/test_realism.py` para el realismo, `tests/test_demo_story.py` para la historia del demo y uno nuevo que exige que cada motivo de carta tenga una cifra como máximo. El detalle de fórmulas y valores está en `docs/formulas.md`, secciones 11 y 12.

---

## La historia del demo (`m001`, ahora semilla 44)

Se mantiene lo esencial: el 1-1 en el 17 y el 63, la misma cadena del empate que el mock con la asistencia invisible de Torres, Torres primero a las 35:00 y al final, y el veredicto «Bahía FC generó más peligro aunque tuvo menos la pelota». Cambian algunos momentos:

| Momento | Qué pasa |
| --- | --- |
| 11:09 | Cota sube al 1.º del MVP |
| 14:10 | Torres sube al 2.º |
| 15:00 | Fase de control de Real Cardón |
| 17:40 | Gol 0-1 de Leyva |
| 19:00 a 40:00 | Torres lidera la carrera MVP (se ve en `data.ranking` de cada `mvp_update`) |
| 45:00 | Claves del medio tiempo |
| 43:00 a 68:00 | Cota lidera |
| 63:09 | Gol 1-1 de Ramírez, asistencia invisible de Torres |
| 77:00 | Fase de presión de Bahía (antes no salía) |
| 79:06 | Torres sube al 1.º |
| 90:00 | Top 3: Torres, Cota y Salgado (el mock dice Torres, Cota y Rosas) |

**Para el guion del video:** no hay un aviso «Torres sube al primer lugar» antes de las 35:00. Torres llega ahí cuando Cota baja, y esos cambios no se anuncian. Para «¿Por qué Torres va primero?» conviene mostrar la carrera MVP, donde sí aparece primero.

---

## Integrante 2, agentes (Diego)

Ningún cambio de código es obligatorio. Se probó en local, sin tocar sus archivos: sus plantillas pasan `check_variant` con los 63 insights nuevos de `m001`, los 15 del mock y 482 de 10 partidos libres.

- [ ] **Regenerar `data/m001/overlays.json` y `agents_report.json`** con `python -m baja_agents run`, una sola vez, después del merge. Las órdenes actuales apuntan a insights que ya cambiaron. Si ya agregaste el ranking a mano, igual hay que regenerar.
- [ ] **Actualizar los tests que buscan insights de `m001` por identificador.** Mientras no se actualicen, el job `agents` de la CI va a fallar. Equivalencias, comprobadas con las mismas aserciones de sus tests y con `checks.py` tal como está en `main`:

| Antes | Ahora | Qué es | Cambia en el test |
| --- | --- | --- | --- |
| `i01` | `i01` | Duelo Lugo contra Montaño, sin cambio de signo | Nada |
| `i02` | `i11` | Control de Real Cardón | «62% de posesión entre 05:00-15:00» en vez de «64%… 01:00-11:00» |
| `i07` | `i07` | Carta (ahora de Regate de Cota) | Nada, solo valida el esquema |
| `i22` | `i25` | MVP mientras va 0-1 (Leyva, minuto 30) | El nombre del texto: Leyva en vez de Montaño |
| `i26` | `i34` | Claves del medio tiempo | Posesión `{"Bahía FC": 43, "Real Cardón": 57}`; D. Mena ya no aparece, usar J. Torres o B. Haro en `who_is_who` |
| `i38` | `i44` | Gol del 1-1 con la asistencia invisible de Torres | Nada más que el identificador |
| `i46` | `i35` | Hito de Cota, minuto 45 | 10 recuperaciones y 4 pases progresivos en vez de 12 y 16; el caso de pase clave mal etiquetado queda «4 pases clave» |

- [ ] **Agente Pregúntale:** las cifras de `m001` cambian, así que las respuestas de ejemplo de `mocks/chat_tools_sample.json` ya no coinciden con el partido. Eso ya pasaba antes con algunas cifras: el mock es un ejemplo, no el partido real.

---

## Integrante 3, interfaz (luismar)

Ningún cambio de código. Los tipos ya incluyen los 7 atributos de carta y todas las posiciones.

- [ ] **`mocks/teams.json`:** O. Félix (MC, Bahía FC) ahora es **titular**, porque Bahía jugaba con 10. Si la interfaz muestra alineaciones, aparecerá. También cambiaron los valores de `role_baselines_per_90`, que la interfaz no usa.
- [ ] **Cartas de Ritmo, Regate y Sin balón:** antes nunca salían y ahora sí. Conviene revisar que se vean bien.
- [ ] **Grabar el video con las órdenes regeneradas** por Diego, no con las actuales.
- [ ] Sigue pendiente, como antes: el motivo de la carta llega en español también en las órdenes en inglés.

---

## Orden sugerido

1. Merge de `motor-realism`. El job `test` pasa; el job `agents` fallará en los tests de la tabla de arriba hasta que Diego los actualice.
2. Diego actualiza sus tests y regenera las órdenes, idealmente en el mismo día.
3. Datos congelados: nadie cambia `m001` hasta después de grabar el video.
