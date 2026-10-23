# Interfaz, integrante 3

Aquí va la interfaz web: campo, cartas, carrera MVP, barra de duelo, chat y selector de modo e idioma.

## Entrada

Órdenes de gráfico con la forma de `contracts/overlay.schema.json`. Mientras los agentes no estén listos, reproduce `mocks/overlays_sample.json` con un reloj simulado:

- Muestra cada orden cuando el reloj llega a `show_at_s`, durante `duration_s` segundos y en su `slot`.
- Filtra por el `mode` (`fan` o `analyst`) y el `language` (`es` o `en`) elegidos. Las órdenes con `all` se muestran siempre.
- Las órdenes `duel_bar` con `source_insight: null` son fotogramas para animar la barra entre dos avisos.

## Datos que cambiaron en el contrato v1

Revisa `docs/cambios-contrato-v1.md`. Para la interfaz lo importante es:

- El puntaje se llama `data.mvp_score`, y en el top 3 `data.cards[].mvp_score`.
- En `team_phase` la altura se llama `data.def_action_height_m`.
- La cadena del gol en `goal_analysis` ya viene ordenada por tiempo.

## Validar

```bash
python -m baja_insights validate mocks/overlays_sample.json
```

Desde JavaScript se pueden usar los mismos esquemas con Ajv en modo 2020-12.
