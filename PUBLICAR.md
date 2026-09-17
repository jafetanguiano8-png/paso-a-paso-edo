# Cómo publicar la app en internet (gratis)

Objetivo: que tus alumnos entren desde un link, en cualquier celular o
computadora, sin instalar nada.

Usaremos **GitHub** (para guardar el código) + **Render** (para ponerlo en
línea). Ambos gratis.

---

## Parte 1 — Subir el código a GitHub

### 1.1 Crea una cuenta

Ve a https://github.com y regístrate (usa tu correo institucional si quieres).

### 1.2 Crea un repositorio

En GitHub: botón **+** (arriba a la derecha) → **New repository**.

- **Repository name**: `paso-a-paso-edo`
- Déjalo como **Public**
- **NO** marques "Add a README file" (ya tienes uno)
- Clic en **Create repository**

GitHub te mostrará una página con comandos. No la cierres.

### 1.3 Sube tu proyecto desde la terminal

En tu terminal, dentro de la carpeta del proyecto:

```bash
cd ~/Proyecyo\ ecuaciones\ diferenciales/files

git init
git add .
git commit -m "Primera version de la app"
git branch -M main
```

Ahora conecta con tu repositorio (reemplaza `TU-USUARIO` por tu usuario
de GitHub):

```bash
git remote add origin https://github.com/TU-USUARIO/paso-a-paso-edo.git
git push -u origin main
```

Te pedirá usuario y contraseña. **Importante**: GitHub ya no acepta tu
contraseña normal aquí. Necesitas un "token":

1. Ve a https://github.com/settings/tokens
2. **Generate new token** → **Generate new token (classic)**
3. Ponle un nombre (ej. "mi laptop"), marca la casilla **repo**
4. **Generate token** y **copia el token** (solo se muestra una vez)
5. Cuando la terminal pida contraseña, pega ese token

---

## Parte 2 — Publicar en Render

### 2.1 Crea una cuenta

Ve a https://render.com y regístrate. Elige **Sign up with GitHub** para
que se conecten solos.

### 2.2 Crea el servicio web

1. En el panel de Render: **New +** → **Web Service**
2. Conecta tu repositorio `paso-a-paso-edo`
3. Render debería detectar la configuración sola (por el archivo
   `render.yaml`). Si te pide los datos a mano, usa:
   - **Language / Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**
4. Clic en **Create Web Service**

Espera unos 2-4 minutos mientras construye. Cuando termine verás un link
tipo:

```
https://paso-a-paso-edo.onrender.com
```

**Ese es el link que compartes con tus alumnos.**

---

## Cosas que debes saber del plan gratuito

- **La app se duerme** tras 15 minutos sin que nadie la use. El primer
  alumno que entre después esperará entre 30 y 60 segundos a que
  despierte; a partir de ahí va rápido para todos.
  - Truco para clase: entra tú al link 2 minutos antes de empezar, así ya
    está despierta cuando lleguen tus alumnos.
- **Es pública**: cualquiera con el link puede entrar. No hay datos
  personales en la app, así que no hay problema.
- Si el link se cae o quieres cambiar algo, ve al panel de Render.

---

## Cómo actualizar la app después

Cada vez que cambies algo en tu computadora:

```bash
git add .
git commit -m "describe aqui tu cambio"
git push
```

Render detecta el cambio y vuelve a publicar automáticamente en 2-3
minutos. No tienes que hacer nada más.

---

## Compartirla con tus alumnos

Opciones:

1. **Pegar el link en Moodle** (universidad virtual), como recurso tipo
   "URL" dentro del curso.
2. **Mandarlo por correo institucional**.
3. **Generar un código QR** del link (hay generadores gratis en línea) y
   proyectarlo en clase para que lo escaneen con el celular.

Diles que pueden agregarlo a la pantalla de inicio de su celular
(en Chrome: menú ⋮ → "Agregar a pantalla de inicio") para que les quede
como si fuera una app.
