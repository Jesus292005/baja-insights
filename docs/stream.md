# Servicio de stream (contrato v1.1, cambio 7)

WebSocket que le manda a la interfaz el reloj, el marcador y las órdenes de gráfico de un partido. Código en `src/baja_insights/stream/`, sin dependencias fuera de la biblioteca estándar.

```bash
python -m baja_insights serve --data data --port 8080 --speed 60
```

Carga cada `data/<partido>/events.jsonl`, con su `overlays.json` si existe. Hoy son `m001` (119 órdenes) y `f002` (sin órdenes, solo reloj y marcador). `GET /healthz` responde `ok` para las sondas de Container Apps. Cualquier otra ruta con `Upgrade: websocket` abre el stream.

## Mensajes

Todos son JSON con `type`. La forma vive solo en `stream/messages.py`, así que ajustarse al `stream.schema.json` final es cambiar ese archivo.

| `type` | Sentido | Campos |
| --- | --- | --- |
| `subscribe` | UI → servidor | `match_id`, `from_t_s` (entero o `null`) |
| `state` | servidor → UI | `t_s`, `home`, `away`, `scoreline` |
| `overlay` | servidor → UI | `order`, que valida con `overlay.schema.json` |
| `clock` | servidor → UI | `t_s`, `period`, `phase` (`first_half`, `second_half`, `full_time`), `speed` |
| `error` | servidor → UI | `code` (`invalid_message`, `match_not_found`), `detail` |

## Cómo se comporta

- **Un reloj por partido**, compartido por todos los que lo ven, como en una transmisión en vivo. Arranca con el primer `subscribe` en `--start-at` (0 por defecto) y avanza `--speed` segundos de partido por segundo real. Sigue hasta 5520 para que salgan los gráficos del final, y luego se queda ahí. Para repetir el partido se reinicia el servicio.
- **Al suscribirse** el servidor manda, en este orden: `state` del minuto actual, las órdenes que le faltan al cliente y un `clock`.
- **Después** manda cada orden cuando el reloj llega a su `show_at_s`, aunque `speed` sea alta. Manda un `state` en cada `goal`, `half_time` y `match_end`, y un `clock` por cada segundo real, que sirve de latido.
- **Marcador.** Sale solo de los eventos. Nunca se deduce de las órdenes.
- **Reconexión.** Con `from_t_s`, se reenvían las órdenes ya vencidas que el cliente no terminó de ver: `show_at_s + duration_s > from_t_s`. Así vuelve un gráfico que estaba en pantalla cuando se cortó la conexión, como un `goal_analysis` de 12 s o el `top3` de 20 s. Con la regla `show_at_s ≥ from_t_s` de la propuesta se perdería. Sin `from_t_s` (primera conexión), solo llega lo que está en pantalla en ese momento.
- Se mandan las cuatro variantes de cada orden. La UI filtra por `mode` y `language`.

## Despliegue en Azure Container Apps

```bash
az acr build -r <registro> -f stream.Dockerfile -t baja-stream:latest .
az containerapp create -n baja-stream -g <grupo> --environment <entorno> \
  --image <registro>.azurecr.io/baja-stream:latest --ingress external --target-port 8080 \
  --env-vars STREAM_SPEED=1 --min-replicas 1 --max-replicas 1
```

Una sola réplica, porque el reloj vive en memoria y dos réplicas tendrían dos relojes. `--min-replicas 1` evita que escale a cero y reinicie el partido. El ingreso HTTP de Container Apps acepta WebSocket sin configuración extra. La UI se conecta a `wss://<app>.<región>.azurecontainerapps.io/ws`.

## Pendiente

- Comparar `messages.py` con el `stream.schema.json` del PR de la interfaz, sobre todo los valores de `phase` y los códigos de `error`, que la propuesta no fija.
- Que `python -m baja_insights validate` reconozca mensajes de stream, cuando el esquema esté en el repositorio.
