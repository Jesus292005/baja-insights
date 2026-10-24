# Interfaz, integrante 3

App web y overlay de transmisión de Baja-Insights, en React + TypeScript con Vite. Dibuja las órdenes de gráfico de `contracts/overlay.schema.json` y nunca calcula cifras: toma los números de la orden tal como llegan y, si falta un dato, lo dice.

## Arrancar

Requiere Node 20 o más reciente.

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm test           # tests de la lógica (planificador, selectores, fuentes)
npm run build      # typecheck + build en web/dist
```

Sin servidor, la app repite el partido de demo `data/m001` (órdenes de los agentes y marcador desde los eventos).

## Dos vistas, un build

| Ruta | Para qué |
| --- | --- |
| `/` | App web: escenario 16:9, carrera MVP, duelo, carta del jugador, chat y momentos |
| `/broadcast` | Solo el overlay, 1920×1080 con fondo transparente, para OBS, vMix o cualquier fuente de navegador |

Parámetros de URL:

| Parámetro | Valores | Nota |
| --- | --- | --- |
| `mode` | `fan`, `analyst` | En la app web gana sobre la preferencia guardada |
| `lang` | `es`, `en` | Igual que `mode` |
| `source` | `replay`, `ws` | Por defecto `replay`, o `ws` si existe `VITE_STREAM_URL` |
| `ws` | `wss://…` | URL del stream en vivo |
| `t` | `63:09`, `63` o segundos | Momento inicial de la repetición |
| `speed` | `1` a `120` | Velocidad de la repetición, 60 por defecto |
| `skip` | `0`, `1` | `1`: acelera solo cuando no hay gráfico en pantalla |
| `autoplay` | `0`, `1` | |
| `bug` | `1` | Solo `/broadcast`: dibuja el marcador |

Ejemplo de fuente para OBS: `/broadcast?mode=fan&lang=es&bug=1`. En `/broadcast`, la barra espaciadora pausa la repetición.

## Variables de entorno

| Variable | Qué hace si falta |
| --- | --- |
| `VITE_STREAM_URL` | Se usa la repetición |
| `VITE_ASK_URL` | El chat dice que todavía no está conectado al agente |

## Cómo está hecha

```
src/
  contracts/overlay.ts     tipos del contrato v1.1 (órdenes, stream, chat)
  data/                    partido de demo (módulo virtual de vite.config.ts) y plantel de mocks/teams.json
  stream/                  store, ReplaySource y WebSocketSource (latido, reconexión, reenvío)
  logic/plan.ts            qué orden ocupa cada slot en cada segundo: cola, prioridad y pausas
  logic/derive.ts          selectores del rail: duelo, MVP, cartas y momentos (solo copian valores)
  components/stage/        lienzo 1920×1080 y un gráfico por tipo de orden
  components/rail/         paneles de la app web y el chat
  design/tokens.css        tokens de la dirección visual Litoral
  i18n/strings.ts          textos de la interfaz en español e inglés
```

- **Slots.** Una orden por slot; la siguiente espera. `full_screen` pausa todo y `center` pausa `side_panel` y `lower_third`. Una orden que espera más de 20 s se descarta, salvo goles, claves y top 3.
- **Cifras.** Se muestran como llegan, sin quitar decimales ni animar el conteo. Solo la geometría (la barra del duelo) se interpola entre dos valores reales.
- **Marcador.** Sale de los eventos con `scoreline` (en vivo, del mensaje `state`), nunca de las órdenes.
- **Estados.** Cargando con esqueletos del mismo tamaño, vacío con texto honesto, reconectando con el último dato y su minuto, y sin conexión con botón para reintentar.

## Desplegar en Azure Static Web Apps

`app_location: web`, `output_location: dist` y sin `api_location`. `public/staticwebapp.config.json` resuelve `/broadcast` y las rutas del cliente. El build lee `../data` y `../mocks`, así que necesita el repositorio completo, que es lo que hace la acción de GitHub de Static Web Apps.

## Pendiente del lado de los datos

- `mvp_update` no trae el nombre del jugador. Hasta que los agentes copien `data.ranking` (v1.1), la carrera muestra cada movimiento con el título del agente y no un ranking.
- `team_phase` no dice a qué equipo pertenece un número suelto, así que la UI lo muestra sin atribuirlo.
- Los demás campos de v1.1 (`evidence`, `overall_to`, `chain_detail`) se muestran en cuanto lleguen; mientras tanto la carta dice «Media sin dato».
