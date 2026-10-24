# Despliegue en Azure

Todo vive en la suscripción Azure for Students del integrante 2, junto al recurso de Foundry, porque una identidad administrada no puede pedir tokens para un Foundry de otro tenant.

| Recurso | Nombre | Notas |
| --- | --- | --- |
| Grupo de recursos | `rg-baja-insights` | Región `centralus` |
| Foundry | `diegomanzo-2526-resource`, proyecto `diegomanzo-2526` | Modelo `gpt-4.1-mini-baja-insights` |
| Entorno de Container Apps | `baja-env` | Con su Log Analytics `workspace-rgbajainsightsA2tF` |
| Servicio de stream | `baja-stream` | Una réplica fija (`min` y `max` en 1), 0.25 vCPU y 0.5 GiB |

**URL del stream:** `wss://baja-stream.victoriouswater-634aa14d.centralus.azurecontainerapps.io/ws`

Hoy corre la imagen de ejemplo de Microsoft (`mcr.microsoft.com/k8se/quickstart`) para que la URL ya exista. El stream real entra con los pasos de abajo.

## Por qué ghcr.io y no Azure Container Registry

Las suscripciones Azure for Students no permiten ACR Tasks (`TasksOperationsNotAllowed`), así que `az acr build` no funciona, y ningún integrante tiene Docker local. La imagen se construye en GitHub Actions (`.github/workflows/stream-image.yml`) y se publica en GitHub Container Registry, que es gratis.

- Cada push a `main` que toque `src/`, `data/`, `stream.Dockerfile` o `.dockerignore` publica `ghcr.io/jesus292005/baja-stream` con las etiquetas `latest` y `sha-<commit>`.
- En los PR solo se construye la imagen, sin publicarla, para detectar un Dockerfile roto antes del merge.
- También se puede lanzar a mano desde la pestaña Actions ("Stream image" → "Run workflow").

## Pasar a la imagen real (una sola vez)

1. **Publicar la primera imagen.** Hacer merge a `main` del PR que trae el workflow, o lanzarlo a mano.
2. **Hacer pública la imagen.** El paquete queda a nombre del dueño del repo (`Jesus292005`), así que lo hace él: en GitHub, Packages → `baja-stream` → Package settings → Change visibility → Public. Si queda privado, Container Apps no puede descargarlo sin credenciales.
3. **Cambiar la imagen y el puerto** (dueño de la suscripción, en Git Bash con `export MSYS_NO_PATHCONV=1`):

```bash
az containerapp ingress update -n baja-stream -g rg-baja-insights --target-port 8080
az containerapp update -n baja-stream -g rg-baja-insights --image ghcr.io/jesus292005/baja-stream:latest
```

4. **Probar:**

```bash
curl https://baja-stream.victoriouswater-634aa14d.centralus.azurecontainerapps.io/healthz
```

Responde `ok`.

## Publicar una versión nueva

Después de cada merge a `main` que cambie el motor o los datos, por ejemplo un `overlays.json` regenerado, se despliega con la etiqueta del commit. Con `latest`, Container Apps no siempre vuelve a descargar la imagen.

```bash
az containerapp update -n baja-stream -g rg-baja-insights --image ghcr.io/jesus292005/baja-stream:sha-<commit corto>
```

Cada `update` crea una revisión nueva y reinicia el servicio, así que el reloj del partido vuelve a empezar.

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
