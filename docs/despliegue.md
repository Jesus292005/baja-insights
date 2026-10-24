# Despliegue en Azure

Todo vive en la suscripción Azure for Students del integrante 2, junto al recurso de Foundry, porque una identidad administrada no puede pedir tokens para un Foundry de otro tenant.

| Recurso | Nombre | Notas |
| --- | --- | --- |
| Grupo de recursos | `rg-baja-insights` | Región `centralus` |
| Foundry | `diegomanzo-2526-resource`, proyecto `diegomanzo-2526` | Modelo `gpt-4.1-mini-baja-insights` |
| Entorno de Container Apps | `baja-env` | Modo `WorkloadProfiles`, perfil `Consumption`, con su Log Analytics `workspace-rgbajainsightsA2tF` |
| Servicio de stream | `baja-stream` | Imagen `ghcr.io/jesus292005/baja-stream:sha-c81b433`, una réplica fija (`min` y `max` en 1), 0.25 vCPU y 0.5 GiB |

**URL del stream:** `wss://baja-stream.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/ws`

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
```

## El chat, después

Cuando exista `POST /api/ask`, el contenedor que lo sirva necesita una identidad administrada con el rol **Foundry User** sobre `diegomanzo-2526-resource`. Los comandos están en `agents/README.md`, en "Credentials and deployment".
