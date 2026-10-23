# Datos de ejemplo de Baja-Insights, contrato v1

Estos archivos sirven para que cada integrante avance **sin esperar a los demás**. Son datos escritos a mano que respetan los esquemas de `contracts/`. El partido real generado por el motor está en `data/m001/` con la misma forma, así que cambiar de fuente es cambiar una ruta.

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
| **chat_tools_sample.json** | Las 6 funciones de consulta de Pregúntale al partido y 6 conversaciones de ejemplo | Integrante 2 y el chat de la interfaz |

---

## Cómo usarlos

**Integrante 1, motor.** El generador y el motor ya producen archivos con exactamente esta forma. `tests/test_engine.py` comprueba que, al recibir estos eventos, el motor reproduce las cadenas de gol, la subida de Torres al primer lugar y las cartas de estos insights.

**Integrante 2, agentes.** Cargar `insights_sample.json` y mandarlos uno por uno al curador como si llegaran en vivo. La salida de los agentes debe tener la forma de `overlays_sample.json`. Las funciones del chat ya están implementadas en `src/baja_insights/engine/tools.py`. Usa las conversaciones de `chat_tools_sample.json` como casos de prueba.

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

## Cambios respecto a la versión anterior

La lista completa, con el motivo de cada cambio y los números que se recalcularon, está en `docs/cambios-contrato-v1.md`. La referencia de todos los campos está en `contracts/README.md`.

Para revisar que un archivo cumpla el contrato:

```bash
python -m baja_insights validate mocks/insights_sample.json
```
