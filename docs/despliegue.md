# Despliegue en Azure

Todo vive en la suscripción Azure for Students del integrante 2, junto al recurso de Foundry, porque una identidad administrada no puede pedir tokens para un Foundry de otro tenant.

| Recurso | Nombre | Notas |
| --- | --- | --- |
| Grupo de recursos | `rg-baja-insights` | Región `centralus` |
| Foundry | `diegomanzo-2526-resource`, proyecto `diegomanzo-2526` | Modelo `gpt-4.1-mini-baja-insights` |
| Entorno de Container Apps | `baja-env` | Modo `WorkloadProfiles`, perfil `Consumption`, con su Log Analytics `workspace-rgbajainsightsA2tF` |
| Servicio de stream | `baja-stream` | Imagen `ghcr.io/jesus292005/baja-stream:sha-7048698` (motor del PR #11 y las 168 órdenes de `m001` del PR #12), una réplica fija (`min` y `max` en 1), 0.25 vCPU y 0.5 GiB |
| Servicio del chat | `baja-chat` | `POST /api/ask`, `POST /api/chat-overlay` y `POST /mcp`, imagen `ghcr.io/jesus292005/baja-chat:sha-623edcc` (PR #19). Una réplica fija (`min` y `max` en 1), 0.5 vCPU y 1 GiB, con identidad del sistema y el rol Foundry User |

**URL del stream:** `wss://baja-stream.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/ws`

**URL del chat:** `https://baja-chat.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/api/ask`

Probado en Azure: `/healthz` responde `ok`, una petición inválida recibe 400, y las preguntas reales responden con la identidad administrada (sin claves), cumpliendo `chat.schema.json`. Una pregunta nueva tarda de 3 a 9 s, y una repetida sale de la caché en milisegundos.

Probado: `/healthz` responde `ok`, el WebSocket abre y, al suscribirse a `m001`, llegan `state` y un `clock` por segundo. Todos los mensajes validan con `stream.schema.json`.

## No usar un entorno «express»

Con la extensión `containerapp` en preview, `az containerapp env create` sin `--environment-mode` crea un entorno **express**. Ahí el contenedor arranca, pero nunca queda listo: el ingreso no responde, no llegan logs a Log Analytics y no se aceptan sufijos de revisión. El primer `baja-env` era así, y por eso cambió la URL. Hay que crearlo con el modo explícito:

```bash
az containerapp env create -n baja-env -g rg-baja-insights -l centralus --environment-mode WorkloadProfiles   --logs-workspace-id <customerId> --logs-workspace-key <clave>
az containerapp create -n baja-stream -g rg-baja-insights --environment baja-env --workload-profile-name Consumption   --image ghcr.io/jesus292005/baja-stream:sha-<commit corto> --ingress external --target-port 8080   --min-replicas 1 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --env-vars STREAM_SPEED=1 STREAM_HALF_TIME_PAUSE=0
```

`az containerapp create` puede devolver `InternalServerError` aunque el container app sí se crea. Antes de repetirlo, revisa con `az containerapp show`.

## Por qué ghcr.io y no Azure Container Registry

Las suscripciones Azure for Students no permiten ACR Tasks (`TasksOperationsNotAllowed`), así que `az acr build` no funciona, y ningún integrante tiene Docker local. La imagen se construye en GitHub Actions (`.github/workflows/stream-image.yml`) y se publica en GitHub Container Registry, que es gratis.

- Cada push a `main` que toque `src/`, `data/`, `stream.Dockerfile` o `.dockerignore` publica `ghcr.io/jesus292005/baja-stream` con las etiquetas `latest` y `sha-<commit>`.
- En los PR solo se construye la imagen, sin publicarla, para detectar un Dockerfile roto antes del merge.
- También se puede lanzar a mano desde la pestaña Actions ("Stream image" → "Run workflow").

## Imagen pública

El paquete `ghcr.io/jesus292005/baja-stream` está a nombre del dueño del repo (`Jesus292005`) y ya es público: se descarga sin credenciales. Si alguna vez quedara privado, Container Apps no podría descargarlo. Se cambia en GitHub, en Packages → `baja-stream` → Package settings → Change visibility.

Para probar el servicio:

```bash
curl https://baja-stream.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/healthz
```

Responde `ok`.

## Publicar una versión nueva

Después de cada merge a `main` que cambie el motor o los datos, por ejemplo un `overlays.json` regenerado, se despliega con la etiqueta del commit. Con `latest`, Container Apps no siempre vuelve a descargar la imagen.

```bash
az containerapp update -n baja-stream -g rg-baja-insights --image ghcr.io/jesus292005/baja-stream:sha-<commit corto>
```

Cada `update` crea una revisión nueva y reinicia el servicio, así que el reloj del partido vuelve a empezar. En Git Bash, corre antes `export MSYS_NO_PATHCONV=1`.

**El reloj es compartido.** Arranca con el primer `subscribe` y, a `STREAM_SPEED=1`, el partido dura 90 minutos reales y luego se queda en el final. Para dejarlo listo antes de una demo o de que entren los jueces, reinícialo:

```bash
az containerapp revision restart -n baja-stream -g rg-baja-insights --revision $(az containerapp show -n baja-stream -g rg-baja-insights --query properties.latestRevisionName -o tsv)
```

## Costo

- **Container app:** una réplica siempre encendida de 0.25 vCPU y 0.5 GiB. Son centavos por día, en buena parte cubiertos por la cuota gratuita mensual de Container Apps.
- **Log Analytics:** se paga por GB de logs, que aquí son casi nada.
- **ghcr.io:** gratis para paquetes públicos.

Para apagarlo después del 10 de noviembre:

```bash
az containerapp delete -n baja-stream -g rg-baja-insights --yes
az containerapp delete -n baja-chat -g rg-baja-insights --yes
```

## El chat

`baja-chat` es un container app propio, separado del stream:

- El stream no puede tener más de una réplica, porque su reloj vive en memoria.
- Cada redespliegue del chat reiniciaría el reloj del partido.
- El stream usa solo la biblioteca estándar, mientras que el chat necesita Agent Framework y Azure.

**Ya está listo:**
- El container app existe en `baja-env`, con perfil `Consumption`.
- Tiene una identidad administrada del sistema con el rol **Foundry User** sobre `diegomanzo-2526-resource`. Los agentes la usan con `DefaultAzureCredential` y no necesitan claves.
- Una réplica fija, para que nadie espere el arranque del contenedor (unos 13 s) durante la grabación del video y mientras los jueces prueban.

**El servicio** (Pregúntale al partido, ver `agents/README.md`):
- Código en `agents/baja_agents/ask.py` y `server.py`.
- Imagen `chat.Dockerfile`, con sus exclusiones propias en `chat.Dockerfile.dockerignore`, porque el `.dockerignore` del repo deja fuera `agents/`.
- El workflow `.github/workflows/chat-image.yml` publica `ghcr.io/jesus292005/baja-chat` en cada push a `main` que toque los agentes, el motor, los datos, los mocks o los contratos.

**Cómo se desplegó (y cómo publicar una versión nueva):**

1. El paquete `ghcr.io/jesus292005/baja-chat` ya es público. Si alguna vez quedara privado, el dueño del repo lo cambia, igual que con `baja-stream`.
2. Cambiar el puerto antes que la imagen, para que la revisión nueva nazca con las sondas en el 8080:

```bash
az containerapp ingress update -n baja-chat -g rg-baja-insights --target-port 8080
az containerapp update -n baja-chat -g rg-baja-insights --image ghcr.io/jesus292005/baja-chat:sha-<commit corto> --set-env-vars FOUNDRY_PROJECT_ENDPOINT=https://diegomanzo-2526-resource.services.ai.azure.com/api/projects/diegomanzo-2526 FOUNDRY_MODEL=gpt-4.1-mini-baja-insights CHAT_PER_MINUTE=20
```

3. Probar:

```bash
curl https://baja-chat.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/healthz
```

**Réplica fija.** Corre con `--min-replicas 1 --max-replicas 1` desde el 24 de octubre. Con `min-replicas 0` no cobraría mientras nadie pregunta, pero la primera pregunta después de un rato esperaría unos 13 s a que arranque el contenedor (Python, Agent Framework y la carga de los partidos). Una réplica fija cuesta centavos por día. Después del 10 de noviembre se puede volver a escala a cero o borrar. La caché de respuestas vive en `/tmp` y se pierde al reiniciar.

**Servidor MCP.** El mismo servicio expone las seis funciones del motor como servidor MCP en `POST /mcp`. Se probó con el cliente MCP de Agent Framework en la CI y, en Azure el 24 de octubre, con `initialize`, `tools/list` y `tools/call` (con `as_of`). Los detalles están en `agents/README.md`, en la sección «MCP server»:

```text
https://baja-chat.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/mcp
```

No usa el modelo, así que no gasta tokens ni cuenta para el límite de preguntas del chat.

**Respuestas en pantalla.** `POST /api/chat-overlay` convierte una respuesta de `/api/ask` en una orden `chat_answer` (ver `agents/README.md`). Se probó en Azure con una respuesta real, y la orden cumple `overlay.schema.json`.

Para comprobar el rol:

```bash
az role assignment list --assignee $(az containerapp identity show -n baja-chat -g rg-baja-insights --query principalId -o tsv) --all -o table
```
