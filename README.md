# Paso a paso — Ecuaciones Diferenciales (prototipo)

Este es un prototipo funcional: tú escribes el lado derecho de una ecuación
`dy/dx = ...` y la app te muestra la solución **paso a paso** (por ahora,
solo ecuaciones de variables separables).

No necesitas subir nada a App Store ni Google Play: es una página web que
corre en tu computadora, y desde el celular la abres en el navegador (o la
"instalas" a la pantalla de inicio).

## 1. Instalar lo necesario (una sola vez)

Necesitas Python 3.10 o más nuevo instalado. Luego, en una terminal, dentro
de esta carpeta:

```bash
pip install -r requirements.txt
```

## 2. Correr la app

```bash
uvicorn main:app --reload
```

Verás un mensaje como `Uvicorn running on http://127.0.0.1:8000`.

Abre esa dirección en tu navegador: **http://localhost:8000**

## 3. Abrirla desde tu celular (misma red WiFi)

1. En tu computadora, busca tu IP local (en Windows: `ipconfig`, en
   Mac/Linux: `ifconfig` o `ipconfig getifaddr en0`). Algo como
   `192.168.1.25`.
2. Corre el servidor así, para que acepte conexiones de otros dispositivos:
   ```bash
   uvicorn main:app --host 0.0.0.0 --reload
   ```
3. En tu celular (conectado a la misma WiFi), abre en el navegador:
   `http://192.168.1.25:8000` (con tu IP real).
4. En Chrome/Safari puedes "Agregar a pantalla de inicio" para que se sienta
   como una app.

## Qué incluye este prototipo

Resuelve ecuaciones diferenciales de primer orden de 5 tipos, mostrando el
procedimiento paso a paso:

- **Variables separables**
- **Lineales** (factor integrante)
- **Homogéneas** (sustitución y = vx)
- **Bernoulli** (sustitución v = y¹⁻ⁿ)
- **Exactas** (M dx + N dy = 0) — para este tipo, escribe la ecuación
  completa como `M + N*dy/dx = 0`, por ejemplo:
  `2*x*y + (x^2+3*y^2)*dy/dx = 0`

Puedes dejar que la app elija el método automáticamente, o forzar uno en
particular con los botones de arriba (útil cuando una ecuación admite más
de un método y quieres mostrarle a tus alumnos uno específico).

Archivos:
- `main.py` — el motor matemático (Python + SymPy).
- `static/index.html` — la interfaz visual (una sola página con KaTeX).

## Siguientes pasos sugeridos

1. Agregar más tipos: ecuaciones reducibles a homogéneas, factores
   integrantes especiales para ecuaciones no exactas.
2. Agregar una gráfica del campo de pendientes o de la solución.
3. Guardar un historial de ecuaciones resueltas.
4. Si más adelante quieres una app instalable "de verdad" en App
   Store/Google Play, este mismo `main.py` puede quedarse igual como backend,
   y solo se cambiaría el frontend por una app en Flutter.
