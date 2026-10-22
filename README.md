# oldreds-festival

La página del Festival Infantil de Old Reds. Se publica en
https://oldreds-festival.vercel.app, el mismo link del QR que se repartió en
julio.

- `index.html`: festival del **sábado 24 de octubre de 2026** (Cancha UC,
  canchas 1 a 11). Generado desde la programación en PDF
  (`assets/programacion_2026-10-24.pdf`) con `generator/armar_octubre.py`,
  que usa la página de julio como plantilla.
- `2026-julio/`: festival del 25 de julio de 2026, como registro. Esa edición
  también vive en el sitio del club, en
  https://oldreds.vercel.app/festival/2026-julio.

Hasta el 22 de octubre de 2026 este proyecto solo redirigía (307) al sitio del
club. Se sacó `vercel.json` para volver a servir el festival desde acá; la
idea es mantener el festival separado de la app del club por ahora.

Regenerar la página de octubre:

```
python3 generator/armar_octubre.py assets/programacion_2026-10-24.pdf 2026-julio/index.html index.html
```
