# El partido sin guion `f091`: cómo integrarlo y qué le toca a cada quien

**Objetivo:** que en la web, con gráficos, carrera del MVP, duelos, cartas y chat, se pueda ver un partido **sin guion**, jugado por el generador de decisiones. `m001`, el partido con guion, se queda como está.

## Dónde estamos

| Rama | Estado |
| --- | --- |
| `main` | Ya tiene la dinámica (PR #53 y #54) y el chat en Markdown (PR #55) |
| `feature/22-jugadores-dinamica` | Ya tiene los primeros 3 commits del generador de decisiones (PR #56) |
| `feature/generador-decisiones` | Tiene, además, la lectura de la presión, el tiro de primera, los contragolpes y el partido `data/f091` |

**`feature/22-jugadores-dinamica` ya entró a `main`, así que de aquí en adelante todo va contra `main`.** La rama del generador no toca ningún archivo de los que trajo el PR #55, así que no hay conflictos.

Ojo: un merge a `main` publica la web y reconstruye las imágenes del stream y del chat. La web seguirá mostrando `m001` hasta que luismar haga su parte, así que integrar esto no cambia lo que se ve.

## El partido `f091`

Semilla 91, sin guion. Nada está escrito de antemano: el motor y los agentes cuentan lo que pasó.

- **Final 2-2, con remontada de Bahía.** Cardón gana 0-2 con goles de Rosas (21') y Leyva (47'). Bahía empata con Ramírez (54') y un **penal** de Ibarra (78').
- **El partido lo domina Bahía:** 2.31 xG contra 0.87, aunque Cardón tuvo más la pelota (53%).
- **El 1-2 tiene asistencia sin balón:** el desmarque de Salgado arrastra a Meza y abre 7 m. Salgado ya había tocado el balón en esa jugada, así que no es "invisible" en sentido estricto.
- **MVP:** Félix, que le quita el primer lugar a Salgado al final.
- 76 insights.

`tests/test_decisions.py` comprueba que `data/f091` coincide con lo que genera el código. Si el generador vuelve a cambiar, hay que regenerarlo, y Diego regenerar sus órdenes.

---

## Integrante 1 (motor)

- [x] Generador de decisiones, penales y contrato. Ya están en `feature/22-jugadores-dinamica` (PR #56).
- [x] Lectura de la presión, tiro de primera, contragolpes, centros y puntería.
- [x] `data/f091` (eventos, insights y posiciones) y sus pruebas.
- [ ] Abrir el PR de `feature/generador-decisiones` contra **`main`** y hacer merge cuando la CI esté en verde.
- [ ] Cuando Diego suba las órdenes de `f091`, agregarlas a `tests/test_contracts.py`.

## Diego (agentes)

**1. Órdenes de `f091` con el modelo.** En una rama sacada de `main` después del merge, desde `agents/`:

```powershell
venv\Scripts\python.exe -m baja_agents run --insights ..\data\f091\insights.json
```

Escribe `data/f091/overlays.json` y `data/f091/agents_report.json`.
- **Presupuesto:** revisa en el reporte que no pase de 250 llamadas.
- **Contrato:** valida con `python -m baja_insights validate data/f091/overlays.json`.
- Revisa que los textos cuenten bien la remontada y el penal.

**2. Probar el chat con `f091`.** El chat carga todos los partidos de `data/`, así que ya debería conocerlo:

```powershell
venv\Scripts\python.exe -m baja_agents ask "¿Quién lidera la carrera al MVP?" --match f091 --at 60:00
```

**3. Opcional:** que el narrador diga "de penal" cuando el remate del gol trae `set_piece: "penalty"`. Hoy el 2-2 sale como un gol sin asistencia.

**4. Producción.** Al hacer merge a `main` se reconstruyen las imágenes del stream y del chat. Despliégalas como dice `docs/despliegue.md`, para que el chat y el stream publicados conozcan `f091`.

## luismar (interfaz)

**1. Elegir cómo se muestra `f091`.** Hoy la web empaqueta un solo partido, el de `BAJA_MATCH`, que por defecto es `m001`.

| Opción | Qué es | Tiempo |
| --- | --- | --- |
| **A. Cambiar el partido de la web** | `BAJA_MATCH: f091` en el paso de build de `.github/workflows/web-deploy.yml`. En local: `$env:BAJA_MATCH = "f091"` antes de `npm run dev` | Minutos |
| **B. Selector de partido** | Que `vite.config.ts` empaquete los dos partidos y la barra tenga "Con guion (m001) / Sin guion (f091)". El chat y el stream ya reciben el `match_id` de la web | 1 a 2 horas |

Si no hay tiempo, la A.

**2. Revisar la web con `f091`** cuando Diego suba las órdenes:
- que nada suponga `m001`: preguntas sugeridas, textos o momentos fijos;
- el balón parado rápido con el penal;
- **opcional:** una etiqueta "Penal" / "Penalty" para `kind: "penalty"` en `set_pieces`.

**3.** Sus pruebas usan `m001` y no cambian.

## Los tres

- [ ] **Decidir qué partido va en el video y en el pitch.**
  - `f091` demuestra que el sistema funciona sin guion: remontada, penal y MVP que nadie eligió.
  - `m001` tiene la asistencia invisible pura de Torres.
  - Si se graba `f091`, revisen el guion del video.

---

## Orden

1. **Integrante 1:** PR de `feature/generador-decisiones` contra `main` y merge.
2. **Diego:** órdenes de `f091` (rama propia, PR contra `main`).
3. **luismar:** en paralelo, la opción A o B (rama propia, PR contra `main`). Para probar mientras Diego termina, puede crear un `data/f091/overlays.json` local con `[]`, sin subirlo.
4. **Los tres:** revisar la web con `f091` completo, decidir el video y desplegar.

## Cómo verlo en local cuando todo esté en `main`

```powershell
cd C:\Users\jesus\Documents\UABC\Baja-Insights\baja-insights
git checkout main
git pull
cd web
npm install
$env:BAJA_MATCH = "f091"
npm run dev
```

Con la opción B no hace falta `BAJA_MATCH`: se elige el partido en la barra.
