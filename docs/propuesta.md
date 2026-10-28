# Baja-Insights — Propuesta definitiva para Inside The Game

**Hackathon:** Inside The Game, Microsoft + Premier League
**Equipo:** 3 integrantes, todos programan, con cuentas de Azure for Students
**Entrega final:** martes 27 de octubre de 2026, 11:59 pm hora del Pacífico. Meta interna: entregar antes de las 6 pm.
**Categorías objetivo:** Best Use of Microsoft Foundry Project y Best Multi-Agent System, además de los premios generales

> **Frase guía:** el marcador no cuenta toda la historia. Nosotros mostramos quién ganó realmente el partido.

---

## 1. El reto en pocas palabras

Construir un sistema que tome los datos de un partido mientras se juega, los convierta en información útil, explique por qué esa información importa y la muestre de forma distinta según quién esté viendo.

- **Datos simulados.** Nosotros generamos los eventos del partido con jugadores y equipos inventados.
- **Explicar es lo central.** No basta con decir "hubo un tiro". Hay que decir por qué ese momento cambió el partido.
- **Debe poder ir en pantalla.** El sistema produce "órdenes de gráfico" que dicen qué mostrar, cuándo y dónde, para que cualquier motor de transmisión las dibuje encima del video.
- **Debe personalizarse.** La misma jugada se cuenta distinto a un analista y a un aficionado casual, y en el idioma de cada quien.

**Cómo cubrimos las cinco etapas que piden las reglas**

| Etapa | Cómo lo cubrimos |
| --- | --- |
| **Ingerir** | Generador sintético que emite eventos en streaming |
| **Interpretar** | Motor de insights en código que detecta y valora cada jugada |
| **Explicar** | Agentes que explican por qué una jugada o un jugador importa |
| **Renderizar** | Órdenes de gráfico en JSON con tiempo y posición, dibujadas por la interfaz web |
| **Personalizar** | Modo analista o aficionado, jugador o duelo elegido e idioma |

---

## 2. Las seis ideas

Las seis ideas no son productos separados. Son seis formas de mostrar lo que detecta un mismo motor.

| # | Idea | Qué ve el aficionado | Momento |
| --- | --- | --- | --- |
| **1** | **Carrera por el MVP** | Ranking en vivo que solo muestra subidas, y al final el top 3 explicado con las jugadas que lo definieron | Durante y al final |
| **2** | **Duelos en vivo** | Barra que indica quién va ganando entre dos jugadores elegidos, medidos contra lo que se espera de su rol | Durante |
| **3** | **Hitos del destacado** | Resumen del aporte de un jugador que está haciendo un gran partido, sobre todo defensas y contenciones | Durante |
| **4** | **Análisis del gol** | Reconstrucción de la jugada y crédito a "la asistencia invisible", incluso sin tocar el balón | Cuando hay gol |
| **5** | **Pregúntale al partido** | Chat que responde con los datos reales del partido, sin inventar | En cualquier momento |
| **6** | **Cartas de jugador** | Carta con atributos que suben durante el partido y dicen por qué, con diseño propio | Formato visual de todas las ideas |

**Cómo se conectan**
- **Un hilo narrativo.** Todo responde a quién ganó realmente el partido. El top 3 es la respuesta final y los duelos, hitos y análisis del gol son las pistas.
- **Un lenguaje visual.** Las cartas son la pieza común. Dos cartas frente a frente en los duelos, la del destacado en los hitos, la del protagonista oculto en el gol y tres cartas en el top 3.
- **Una puerta de entrada.** Con Pregúntale al partido se puede pedir la explicación de cualquier otra idea, por ejemplo "¿quién lidera la carrera al MVP?".
- **Personalización en todas.** Cada idea tiene modo analista con números y modo aficionado con la historia, en el idioma elegido.

---

## 3. Decisiones ya tomadas

- **Jugadores y equipos ficticios** en todo el proyecto y el video. Nada de nombres, logos o diseños de EA FC ni de ninguna otra marca.
- **Sin predicciones de resultado.** No decimos "80% de probabilidad de ganar". Si miramos al futuro será con "claves del partido", es decir, qué necesita cada equipo para ganar.
- **Dos capas.** Las reglas y los cálculos se programan en código normal. La IA no detecta jugadas, las interpreta, decide cuáles mostrar, las explica y las adapta a cada usuario e idioma.
- **En vivo y al final.** Lo rápido sale en vivo. Lo elaborado, como el top 3 y el resumen, sale al medio tiempo y al final. Ambos usan la misma información acumulada.
- **Movimientos sin balón como extra.** Solo en algunas jugadas clave, y nada del sistema depende de ellos.

---

## 4. Prioridades

Seis ideas en cinco días con tres personas es mucho. Este orden asegura que, si el tiempo se acaba, lo entregado ya sea un proyecto completo.

| Nivel | Qué incluye | Por qué |
| --- | --- | --- |
| **Núcleo, obligatorio** | Generador, motor de insights, cartas, carrera por el MVP con top 3, hitos del destacado, modo analista y aficionado, dos idiomas | Cubre las cinco etapas del reto y da el hilo narrativo completo |
| **Núcleo agéntico, obligatorio** | Pregúntale al partido | Es lo que más suma en el criterio de diseño agéntico, que vale 20% |
| **Segundo nivel** | Duelos en vivo | Reutiliza los mismos puntajes, así que cuesta poco una vez que el motor funciona |
| **Tercer nivel** | Análisis del gol con cadena de pases | Usa solo los eventos con balón |
| **Bonus** | Movimientos sin balón y crédito a la asistencia invisible | Requiere simular posiciones extra |

---

## 5. Arquitectura

```
┌──────────────────────────┐
│ Generador sintético      │  Python. Partido evento por evento con
│                          │  jugadas coherentes y jugadores ficticios
└────────────┬─────────────┘
             │ eventos JSON en streaming
             ▼
┌──────────────────────────┐
│ Motor de insights        │  Código, sin LLM.
│                          │  Puntaje por acción, ranking MVP,
│                          │  duelos, hitos, atributos de carta,
│                          │  cadena del gol, estado del partido
└────────────┬─────────────┘
             │ insights + estado compartido
             ▼
┌─────────────────────────────────────────────────────────┐
│ Agentes en Microsoft Foundry con Agent Framework        │
│                                                         │
│  Curador          → decide qué mostrar y cuándo         │
│  Narrador         → explica por qué importa             │
│  Personalización  → adapta a modo e idioma              │
│  Pregúntale       → responde consultando el motor       │
└────────────┬────────────────────────────────────────────┘
             │ órdenes de gráfico JSON
             ▼
┌──────────────────────────┐
│ Interfaz web             │  Campo, cartas, ranking, barra de
│                          │  duelo, chat y selector de modo e idioma
└──────────────────────────┘
```

**Servicios de Azure**
- **Microsoft Foundry** para los modelos y los agentes.
- **Microsoft Agent Framework** para la orquestación multiagente.
- **Azure Container Apps** para el backend, el motor y el streaming por WebSocket.
- **Azure Static Web Apps** para la interfaz.
- **Azure Event Hubs** solo si nos sobra tiempo y queremos sumar en la categoría cloud-native.

---

## 6. Motor de insights

Todo lo que el motor calcula es determinista y reproducible. Así los números siempre son exactos y la IA nunca los inventa.

**Puntaje por acción**
- Cada evento suma o resta puntos según su tipo y su dificultad. Por ejemplo, un pase que rompe líneas bajo presión vale más que un pase lateral sin presión.
- La dificultad del pase considera distancia, presión y líneas rotas. Esto cubre la "calificación de dificultad de pase" que sugieren las reglas.
- Velocidad de tiro y del balón entran como dato en los eventos y en los atributos de la carta.

**Carrera por el MVP**
- Puntaje acumulado ajustado por minutos jugados y por posición, para que no gane solo quien más toca el balón.
- Se emite una orden de gráfico solo cuando alguien sube en el ranking.

**Duelos**
- Cada jugador se compara contra un valor esperado para su rol. La barra muestra la diferencia relativa entre los dos.

**Hitos del destacado**
- Se activan cuando un jugador supera un umbral en recuperaciones, pases clave o duelos ganados, con un tiempo mínimo entre hitos para no saturar la pantalla.

**Cartas**
- Cada jugador tiene atributos base, por ejemplo Visión, Defensa, Ritmo, Disparo y Trabajo sin balón.
- Las acciones destacadas suben atributos con su motivo y minuto, por ejemplo "+2 Visión, pase que rompió dos líneas, minuto 34".

**Análisis del gol**
- Se recorre hacia atrás la cadena de eventos de la posesión que terminó en gol y se asigna crédito a cada acción.

---

## 7. Agentes

| Agente | Entrada | Salida | Cuándo se activa |
| --- | --- | --- | --- |
| **Curador** | Insights nuevos y lo que ya se mostró | Lista de qué mostrar ahora y qué descartar | Cada bloque de eventos o cuando el motor marca algo relevante |
| **Narrador** | Insight elegido y contexto del partido | Explicación de por qué importa, el top 3 explicado y las claves del partido | Cuando el curador elige algo, al medio tiempo y al final |
| **Personalización** | Texto del narrador y perfil del usuario | Versión analista o aficionado, en el idioma elegido | Cada vez que se genera contenido |
| **Pregúntale al partido** | Pregunta del aficionado | Respuesta basada en datos consultados al motor | Cuando el aficionado escribe |

**Pregúntale al partido usa herramientas, no memoria.** El agente tiene funciones que consultan el motor, como el ranking actual, el historial de un jugador, el estado de un duelo o la cadena de un gol. Si el dato no existe, responde que no lo sabe. Exponer esas funciones como un servidor MCP suma puntos en el criterio de diseño agéntico.

**Manejo de fallos.** Si un agente falla o tarda, la interfaz sigue mostrando los datos del motor con un texto de respaldo predefinido. El partido nunca se queda sin overlays.

---

## 8. Esquemas

Estos formatos se acuerdan el primer día para que los tres trabajen en paralelo.

**Evento de entrada**

```json
{
  "match_id": "m001",
  "event_id": 1543,
  "minute": 63,
  "second": 12,
  "type": "pass",
  "team": "Bahía FC",
  "player": "R. Salgado",
  "position": "MC",
  "start": [42.1, 30.5],
  "end": [68.3, 22.0],
  "outcome": "complete",
  "speed_kmh": 54.2,
  "under_pressure": true,
  "lines_broken": 2,
  "possession_id": 211
}
```

**Tipos de evento:** `pass`, `shot`, `tackle`, `recovery`, `duel`, `possession_change`, `pressure`, `foul`, `goal`, `substitution`, `off_ball_run`, `match_start`, `half_time`, `match_end`

**Coordenadas:** campo de 105 por 68 metros, con el origen en la esquina inferior izquierda.

**Orden de gráfico de salida**

```json
{
  "match_id": "m001",
  "show_at": "63:12",
  "duration_s": 6,
  "slot": "lower_third",
  "mode": "fan",
  "language": "es",
  "type": "mvp_update",
  "title": "Torres sube al primer lugar",
  "text": "Tercera recuperación en campo rival en diez minutos.",
  "card": { "player": "J. Torres", "attribute": "Defensa", "delta": 2 },
  "data": { "rank": 1, "score": 8.4, "recoveries": 3 }
}
```

**Tipos de orden de gráfico:** `mvp_update`, `duel_bar`, `standout_milestone`, `card_upgrade`, `goal_analysis`, `top3`, `match_keys`, `chat_answer`

---

## 9. Reparto del trabajo

**Integrante 1 — Generador y motor de insights**
- Generador del partido con jugadas coherentes, como rachas de presión, contragolpes y goles después de varios ataques.
- Motor de insights completo, con puntajes, ranking, duelos, hitos, cartas y cadena del gol.
- Funciones de consulta que usará Pregúntale al partido.

**Integrante 2 — Agentes en Foundry**
- Configurar Foundry y verificar región y cuota de la suscripción de estudiante.
- Construir los cuatro agentes, su orquestación con Agent Framework y el servidor MCP o las herramientas de consulta.
- Manejo de fallos, límites de llamadas y caché de respuestas.

**Integrante 3 — Interfaz y presentación**
- Diseño propio de las cartas, ranking MVP, barra de duelo, chat y selector de modo e idioma.
- Mientras el motor avanza, trabaja con órdenes de gráfico de prueba que respeten el esquema.
- Despliegue en Azure, README con diagrama, pitch en inglés y video.

---

## 10. Calendario

| Día | Objetivo |
| --- | --- |
| **Jue 22, noche** | Acordar los dos esquemas, crear el repositorio público, verificar región y cuota de Foundry |
| **Vie 23** | Generador y puntajes funcionando. Interfaz con cartas y ranking usando datos de prueba. Primer agente conectado |
| **Sáb 24** | MVP, hitos y cartas de punta a punta. Curador, narrador y personalización conectados. Duelos si hay tiempo |
| **Dom 25** | Pregúntale al partido funcionando. Integración completa. Grabar un video de respaldo |
| **Lun 26** | Análisis del gol si hay tiempo. Despliegue en Azure. Pulir y corregir errores |
| **Mar 27** | README, pitch, video final y entrega antes de las 6 pm |

Si el lunes en la noche algo del tercer nivel o del bonus no funciona, se queda fuera sin discusión.

---

## 11. Costos estimados en Azure

Cada integrante tiene 100 dólares de crédito. El proyecto debe estar encendido hasta el 10 de noviembre para que los jueces lo prueben.

| Concepto | Estimado |
| --- | --- |
| **Modelos de IA** con GPT-4o mini o GPT-4.1 mini, unos 80 partidos completos entre pruebas y jueces | $15 a $35 |
| **Pregúntale al partido**, unas 500 preguntas en total | Menos de $2 |
| **Container Apps** con escala a cero | $0 a $2 |
| **Static Web Apps** en plan gratuito | $0 |
| **Logs y almacenamiento** | $1 a $2 |
| **Total esperado** | **$20 a $40** |

**Para no gastar de más**
- Pre-generar un partido completo con sus órdenes de gráfico y reproducirlo como si fuera en vivo. Los jueces lo ven sin gastar tokens y el demo es más estable. Solo el chat consume tokens en tiempo real.
- Alerta de presupuesto en Cost Management a los 30 y a los 60 dólares.
- Límite de llamadas por partido en el código.
- Desplegar todo en una sola cuenta y dejar las otras dos de respaldo.
- Confirmar en el catálogo de Foundry qué modelos están disponibles, porque algunos están en proceso de retiro.

---

## 12. Cómo encaja con los criterios de evaluación

Cada criterio vale 20%.

| Criterio | Cómo lo atendemos |
| --- | --- |
| **Implementación técnica** | Generador sintético propio con jugadas coherentes, motor determinista, código ordenado y documentado, Foundry, Agent Framework y Azure |
| **Diseño agéntico e innovación** | Cuatro agentes con roles distintos, estado compartido, herramientas de consulta o MCP, manejo de fallos y un chat que no inventa |
| **Impacto real** | Órdenes de gráfico listas para un motor de transmisión y visibilidad para jugadores que normalmente no lucen |
| **Experiencia y presentación** | Cartas como lenguaje visual común, modos que se sienten distintos y un hilo narrativo claro |
| **Apego a la categoría** | Uso central de Foundry y orquestación multiagente |

---

## 13. Guion sugerido para el video de menos de 2 minutos

El guion final, con los minutos del partido publicado (`f091`) y la narración en inglés, está en [video-script.md](video-script.md). En resumen:

1. **0:00 a 0:12.** La frase guía sobre la cancha con los 22 jugadores.
2. **0:12 a 0:30.** La carrera del MVP: Félix toma el control con Bahía perdiendo 0-2, y una carta que sube un atributo.
3. **0:30 a 0:52.** El gol de Ramírez con su cadena y el desmarque de Salgado, contado en modo aficionado y analista, en español y en inglés.
4. **0:52 a 1:08.** El penal del empate: nadie escribió esta remontada.
5. **1:08 a 1:28.** Pregúntale al partido: "Who leads the MVP race?".
6. **1:28 a 1:42.** El top 3 final.
7. **1:42 a 1:55.** Diagrama de arquitectura con Foundry, Agent Framework, MCP y Azure.

---

## 14. Checklist de entrega

- [ ] Proyecto nuevo, creado después del 29 de septiembre de 2026
- [ ] Repositorio **público** en GitHub
- [ ] Video demo de **menos de 2 minutos** en YouTube o Vimeo
- [ ] El video muestra el proyecto funcionando y el contraste entre modos
- [ ] Sin música con derechos ni marcas, nombres o diseños de terceros
- [ ] Pitch corto con qué construimos, qué tecnologías de Microsoft usamos, qué hace y qué problema resuelve
- [ ] Enlace funcional para que los jueces lo prueben, con credenciales si es privado
- [ ] Todo el material en inglés
- [ ] Formulario completo en la página "Projects" del sitio del hackathon

---

## 15. Riesgos y cómo los manejamos

| Riesgo | Plan |
| --- | --- |
| Demasiadas ideas para el tiempo | Respetar los niveles de prioridad y cortar sin discusión el lunes en la noche |
| Cuota o región bloqueada en la suscripción de estudiante | Verificarlo el jueves y usar otra cuenta del equipo o pedir aumento |
| Puntajes que se sienten injustos o raros en el demo | Calibrar con dos o tres partidos generados antes del sábado |
| Pantalla saturada de overlays | El curador limita cuántas órdenes salen por minuto |
| El chat inventa datos | Solo responde con lo que devuelven las funciones del motor |
| La integración falla el último día | Video de respaldo grabado el domingo |
| Se acaban los créditos | Partido pre-generado, modelo pequeño y alertas de presupuesto |
