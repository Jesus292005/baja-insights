# Servicio de stream (contrato v1.1, cambio 7)

WebSocket que le manda a la interfaz el reloj, el marcador y las órdenes de gráfico de un partido. Sigue `contracts/stream.schema.json`. El código está en `src/baja_insights/stream/`, sin dependencias fuera de la biblioteca estándar.

```bash
python -m baja_insights serve --data data --port 8080 --speed 60 --half-time-pause 5
```

Carga cada `data/<partido>/events.jsonl`, con su `overlays.json` si existe. Hoy son `f091`, el partido sin guion que publica la web (196 órdenes); `m001`, el partido con guion de las pruebas (196 órdenes), y `f002` (sin órdenes, solo reloj y marcador). Cualquier ruta con `Upgrade: websocket` abre el stream; la interfaz usa `/ws`.

Rutas HTTP:

| Ruta | Qué devuelve |
| --- | --- |
| `GET /healthz` | `ok`, para las sondas de Container Apps |
| `GET /positions/<match_id>` | El `positions.json` del partido (`contracts/positions.schema.json`): los 22 jugadores y el balón a 2 cuadros por segundo. Va comprimido con gzip y con CORS abierto, y se carga una sola vez al arrancar. 404 si el partido no tiene posiciones |

## Mensajes

Todos llevan `kind`. Su forma vive solo en `stream/messages.py`.

| `kind` | Sentido | Campos |
| --- | --- | --- |
| `subscribe` | UI → servidor | `match_id`, `from_t_s` |
| `state` | servidor → UI | `match_id`, `t_s`, `home`, `away`, `scoreline` |
| `overlay` | servidor → UI | `order`, que valida aparte con `overlay.schema.json` |
| `clock` | servidor → UI | `match_id`, `t_s`, `period`, `phase`, `speed` |
| `error` | servidor → UI | `code`, `detail` |

- **`phase`.** `live` mientras se juega, `half_time` en el segundo 2700 y durante la pausa del medio tiempo, y `full_time` desde el 5400. `pre` nunca se manda, porque el reloj arranca ya en el saque inicial.
- **`period`.** Vale 1 durante el medio tiempo, como el evento `half_time`.
- **`error`.** `match_not_found` si el partido no existe. `stream_ended` una vez, cuando el reloj llega a 5520 y ya no queda nada por mandar; el latido sigue. `server_error` si algo falla en el servidor, y también si el mensaje de la UI no se puede leer, porque el esquema no tiene un código para eso.

## Cómo se comporta

- **Un reloj por partido**, compartido por todos los que lo ven, como en una transmisión en vivo. Arranca con el primer `subscribe` en `--start-at` (0 por defecto) y avanza `--speed` segundos de partido por segundo real. Con `--half-time-pause N` se detiene N segundos reales en 45:00. Sigue hasta 5520 para que salgan los gráficos del final y se queda ahí. Para repetir el partido se reinicia el servicio.
- **Al suscribirse** el servidor manda, en este orden: `state` del minuto actual, las órdenes que le faltan a la UI y un `clock`.
- **Después** manda cada orden justo cuando el reloj llega a su `show_at_s`, aunque `speed` sea alta. Manda un `state` en cada `goal`, `half_time` y `match_end`, y un `clock` por cada segundo real, que sirve de latido.
- **Marcador.** Sale solo de los eventos. Nunca se deduce de las órdenes.
- **Reconexión.** Se reenvían las órdenes ya vencidas que la UI no terminó de ver: `show_at_s + duration_s > from_t_s`, tal como lo describe `stream.schema.json`. Así vuelven también los gráficos que estaban en pantalla cuando se cortó la conexión, como un `goal_analysis` de 12 s o el `top3` de 20 s, que de otro modo se perderían. Si `from_t_s` falta o es `null`, solo llega lo que está en pantalla.
- Se mandan las cuatro variantes de cada orden. La UI filtra por `mode` y `language`.

Para revisar una sesión grabada (un mensaje por línea):

```bash
python -m baja_insights validate sesion.jsonl
```

Valida cada mensaje con `stream.schema.json` y la orden de cada `overlay` con `overlay.schema.json`. También reconoce peticiones y respuestas de `chat.schema.json`.

## Despliegue en Azure Container Apps

> En la suscripción del proyecto ACR Tasks no está permitido, así que la imagen se construye en GitHub Actions y se publica en ghcr.io. El despliegue real, con sus nombres y URL, está en [despliegue.md](despliegue.md). Los comandos de abajo sirven para una suscripción que sí permita `az acr build`.

```bash
az acr build -r <registro> -f stream.Dockerfile -t baja-stream:latest .
az containerapp create -n baja-stream -g <grupo> --environment <entorno> \
  --image <registro>.azurecr.io/baja-stream:latest --ingress external --target-port 8080 \
  --env-vars STREAM_SPEED=1 STREAM_HALF_TIME_PAUSE=0 --min-replicas 1 --max-replicas 1
```

Una sola réplica, porque el reloj vive en memoria y dos réplicas tendrían dos relojes. `--min-replicas 1` evita que escale a cero y reinicie el partido. El ingreso HTTP de Container Apps acepta WebSocket sin configuración extra. La UI se conecta a `wss://<app>.<región>.azurecontainerapps.io/ws`.
