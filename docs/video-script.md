# Guion del video (menos de 2 minutos)

**Partido:** `f091`, el que publica la web. Bahía FC 2-2 Real Cardón: Cardón gana 0-2 y Bahía remonta con un penal en el 78'. MVP: Félix.

**La narración va en inglés**, porque las reglas piden el material en inglés. Las notas de producción van en español.

**Cómo grabar:** en la página publicada o en local con `BAJA_MATCH=f091`, abrir `/cine?t=MM:SS&autoplay=0`, pulsar F para pantalla completa y grabar la pantalla.
- **Teclas:** Espacio reproduce o pausa. M cambia aficionado/analista. L cambia español/inglés. N y P saltan al siguiente o al anterior momento, 2 s antes de que entre el gráfico.
- La app web (`/`) muestra además la carrera del MVP, las cartas y el chat en el panel lateral. Úsala en las tomas del chat y de la carta.
- **Velocidad:** 2× en juego abierto, 1× cuando entra un gráfico.

**Antes de grabar**, deben estar listos los pasos 1 y 2 de Diego en `docs/pendientes-entrega.md`. Si no, el top 3 del final pone a Salgado primero.

**Sin música con derechos.** Sin marcas, logos ni nombres reales.

---

## Tomas

| Tiempo | En pantalla | Narración (inglés) |
| --- | --- | --- |
| **0:00 – 0:12** | Cancha con los 22 jugadores, a 2×, unos segundos antes del 21' (`/cine?t=21:20`). Marcador 0-0 | *"The scoreboard doesn't tell the whole story. Baja-Insights shows who really won the match: live, explained, and told for every fan."* |
| **0:12 – 0:30** | `t=52:15`. Entra la carrera del MVP: "O. Félix takes control". Luego, en el 54', la carta de Ramírez que sube su disparo | *"A deterministic engine reads every event as it happens. Bahía is 2-0 down, but Félix is winning the ball back everywhere, and the MVP race sees it before the scoreboard does. Player cards level up, each change with its reason."* |
| **0:30 – 0:52** | `t=54:45`. El gol de Ramírez y su análisis: recuperación de Félix, desmarque de Salgado arrastrando a Meza (7 m) y remate. Con el gráfico en pantalla, pulsar **M** y luego **L**: aficionado en español, después analista en inglés | *"Every goal is rebuilt as a chain, crediting the run that dragged a defender and opened seven metres of space. Our agents on Microsoft Foundry write it four ways: for the casual fan or the analyst, in English or Spanish. And they never invent a number: a verifier checks every claim against the data."* |
| **0:52 – 1:08** | `t=77:40`. Recuperación de Ibarra (77:45) y falta de Castro en el área (77:49). El balón parado pasa rápido mientras todos se acomodan para el penal (portero en la línea, los demás fuera del área), y luego el 2-2 de Ibarra (78:55) con su gráfico | *"No script decided this comeback. Our generator plays the match: players press, release the ball under pressure, shoot first time and concede penalties, calibrated against Premier League numbers."* |
| **1:08 – 1:28** | App web (`/`) cerca del 88'. Escribir en el chat: **"Who leads the MVP race?"**. Respuesta: Félix, empatado con Salgado en 8.5. Si da tiempo, **"How was the equaliser built?"** | *"Ask the match anything. The chat answers only through the engine's functions, exposed over MCP, so every answer is real data, and it never reveals what comes next."* |
| **1:28 – 1:42** | `t=89:50`. Entra el top 3 a pantalla completa: Félix, Salgado y Rosas, con las jugadas que lo explican | *"At full time, the top three, explained with the plays that decided it. Félix never scored, and he still won the match for Bahía."* |
| **1:42 – 1:55** | Diagrama de arquitectura del README: generador → motor → agentes (Curator, Narrator, Personalization, Verifier) → órdenes de gráfico → web, overlay de transmisión y chat. Logos o nombres de Foundry, Agent Framework, MCP, Container Apps y Static Web Apps | *"Built on Microsoft Foundry and Agent Framework, with an MCP server, Azure Container Apps and Static Web Apps. The same graphics orders can drive any broadcast engine. Baja-Insights: insight has no borders."* |

**Duración:** unos 1:55. Si se pasa, recorta primero la segunda pregunta del chat y luego la toma de la carta.

## Notas

- **Si Diego agrega la barra de duelo en `f091`:** cámbiala por la carta en la toma de 0:12, y en la narración: *"Duels are measured against what is expected for each role."* Si no, no la menciones.
- **Si el chat tarda en responder,** graba la pregunta, corta la espera y pega la respuesta. El chat publicado tiene una réplica fija, pero la primera pregunta puede tardar unos segundos.
- **Texto en pantalla:** subtítulos en inglés de la narración. Si narran en español, los subtítulos en inglés son obligatorios.
- **Subirlo a YouTube** como público o no listado; las reglas piden un enlace público. Después:
  - pegar el enlace en la página del proyecto en Innovation Studio;
  - pegarlo en la descripción;
  - pegarlo en el README, en `YOUTUBE_VIDEO_URL`.
