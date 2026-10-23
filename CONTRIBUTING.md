# Cómo trabajamos en este repositorio

Somos tres y cada uno avanza sin esperar a los demás. Esta guía existe para que nadie rompa el trabajo de otro.

## Quién es dueño de qué

| Carpeta | Dueño | Los demás |
| --- | --- | --- |
| `src/baja_insights/generator/`, `src/baja_insights/engine/`, `data/` | Integrante 1 | Leen y comentan |
| `agents/` | Integrante 2 | Leen y comentan |
| `web/` | Integrante 3 | Leen y comentan |
| `contracts/`, `mocks/` | Los tres | Cualquier cambio necesita el visto bueno de los tres |
| `docs/`, `README.md` | Los tres | Libre, con PR |

## Flujo con ramas

1. Actualiza `main` antes de empezar: `git pull origin main`.
2. Crea una rama corta con tu prefijo, por ejemplo `motor/calibrar-mvp`, `agentes/curador` o `ui/cartas`.
3. Haz commits pequeños con mensajes claros en español.
4. Abre un PR hacia `main`. La CI corre las pruebas y valida los mocks contra los esquemas.
5. Si tu PR solo toca tu carpeta, puedes hacer merge tú mismo cuando la CI esté en verde.
6. Si toca `contracts/` o `mocks/`, espera la aprobación de los otros dos.

Nada se sube directo a `main`, salvo arreglos de una línea en documentación.

## Cambiar el contrato

1. Edita el esquema en `contracts/`, los mocks que lo usan y el código del motor, todo en el mismo PR.
2. Anota el cambio en `docs/cambios-contrato-v1.md`, o en un archivo nuevo si la versión cambia.
3. Corre `python -m baja_insights validate mocks/*.json` y `python -m pytest`.
4. Avisa en el chat del equipo con el enlace al PR.

## Si trabajas con Claude u otro asistente

- Dale como contexto `contracts/README.md` y el esquema que te toca. Así no inventa campos.
- Pídele que valide su salida con `python -m baja_insights validate`.
- Revisa el diff antes de hacer commit, sobre todo si tocó archivos fuera de tu carpeta.

## Antes de la entrega, el martes 27

- [ ] Repositorio público
- [ ] README en inglés con diagrama
- [ ] Nada de nombres, logos ni música de terceros
- [ ] Sin claves de API en el código. Usen variables de entorno y `.env`, que ya está en `.gitignore`
