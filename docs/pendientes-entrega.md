# Pendientes para la entrega (27 de octubre, noche)

Revisión de `main` en `78caa09`: todos los PR están integrados y la CI está en verde. Quedan dos cosas que solo puede hacer Diego, porque usan su cuenta de Azure, y una revisión final de luismar. El integrante 1 actualiza el README, `docs/stream.md` y el guion del video, en una rama aparte con PR a `main`.

## Diego (agentes y despliegue)

### 1. Regenerar las órdenes de `f091` (obligatorio)

`data/f091/overlays.json` es anterior al arreglo del PR #59, así que el top 3 que se ve al final del partido no coincide con el resto:

| | Hoy en `overlays.json` | Lo que dicen los insights, la carrera del MVP y el chat |
| --- | --- | --- |
| Primer lugar | Salgado | **Félix** (empatados en 8.5; Félix lo toma en el 87' y un empate no se lo quita) |
| Texto de Salgado | "assisted after a run without the ball" | "desmarque que abrió el espacio de un gol": sí había tocado el balón |

Solo cambiaron dos insights: el top 3 (`i75`) y el resumen (`i76`). Con la caché, el resto no pide llamadas nuevas. Desde `agents/`, en una rama sacada de `main`:

```powershell
venv\Scripts\python.exe -m baja_agents run --insights ..\data\f091\insights.json
```

Antes de abrir el PR, revisar:
- en las cuatro versiones del top 3, que `data.cards` ponga a **Félix primero**;
- que ningún texto diga que Salgado no tocó el balón.

Al hacer merge a `main`, la web se publica sola con las órdenes nuevas.

### 2. Desplegar el chat y el stream con el último `main` (obligatorio)

`docs/despliegue.md` dice que corren `sha-e2e2786`, que es de antes del arreglo. En producción, el chat todavía resuelve el empate a favor de Salgado.

Después del paso 1, cuando las imágenes del último commit de `main` estén construidas (workflows *Chat image* y *Stream image* en verde), corre los dos `az containerapp update` de `docs/despliegue.md` con ese `sha-<commit corto>` y actualiza el documento.

El `update` del stream reinicia su reloj. Conviene hacerlo justo antes de grabar o de enviar.

### 3. La barra de duelo no sale en `f091` (recomendado)

En `m001` hay 8 gráficos `duel_bar`; en `f091`, ninguno. El motor sí encontró 9 duelos (`duel_state`: Torres contra Haro, Olvera contra Ruelas, Lugo contra Montaño), pero el curador no eligió ninguno. Como sin un aviso de duelo no hay cuadros de la barra, el reporte dice `duel_frames: 0`.

"Duelos en vivo" es una de las seis ideas del proyecto. Opciones:
- **Regla dura en el curador:** que el primer `duel_state` de cada tiempo siempre salga, como ya pasa con los goles y el top 3. Después hay que regenerar `f091` (paso 1) y quizá `m001`, si cambia.
- **Si no da tiempo:** mostrar la barra de duelo en el video con `m001`, o dejarla fuera del video.

## luismar (interfaz)

### 1. Revisar la página publicada (después de los pasos 1 y 2 de Diego)

https://ambitious-smoke-08207d610.6.azurestaticapps.net

- [ ] Carga `f091`: Bahía FC 2-2 Real Cardón.
- [ ] El top 3 del final pone a **Félix** primero.
- [ ] El chat responde sobre `f091`. Por ejemplo, «Who leads the MVP race?» a partir del 88' debe decir Félix.
- [ ] El modo **En vivo** se conecta y avanza.
- [ ] El penal del 78' se ve bien: el balón parado rápido y la etiqueta, si la agregaste.
- [ ] Modo fan y analista, y español e inglés, en algún gráfico.

### 2. Video

Si te toca grabarlo, el guion está en `docs/video-script.md`, que hace el integrante 1, con los minutos de `f091` que conviene mostrar.

## Integrante 1 (motor)

- [ ] README completo: enlaces, diagrama, 22 jugadores, `f091`, cómo correr la web.
- [ ] `docs/stream.md`: `/positions/<match_id>` y los partidos actuales.
- [ ] `docs/video-script.md`: guion del video en inglés sobre `f091`.
- [ ] Revisar la página publicada cuando Diego termine.

## Orden

1. **Ya, en paralelo:** Diego hace los pasos 1 y 2 (y el 3 si le da tiempo); el integrante 1 hace la documentación.
2. **Cuando Diego termine:** luismar y el integrante 1 revisan la página publicada.
3. **Después:** grabar el video, subirlo a YouTube y enviar el proyecto **antes de las 11:59 pm**.
