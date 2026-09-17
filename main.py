"""
Motor de resolución paso a paso para ecuaciones diferenciales de primer orden
(variables separables y lineales), usando SymPy.

Para correrlo:
    uvicorn main:app --reload
Luego abre http://localhost:8000 en tu navegador (o en el celular si está
en la misma red, usando la IP de tu computadora).

Formato de entrada aceptado:
  - Solo el lado derecho de dy/dx = ...   ej:  "x*y"
  - La ecuación completa                  ej:  "dy/dx + 3*x*y = 6*x"
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Resolvedor paso a paso de EDOs")

x, y, C1, Dy = sp.symbols("x y C1 Dy")
transformations = standard_transformations + (implicit_multiplication_application,)


class Solicitud(BaseModel):
    ecuacion: str
    metodo: str = "auto"  # "auto", "separable" o "lineal"


class Paso(BaseModel):
    titulo: str
    contenido: str  # LaTeX


class Respuesta(BaseModel):
    tipo: str
    pasos: list[Paso]
    solucion: str


def _parse(texto: str):
    return parse_expr(texto, local_dict={"x": x, "y": y, "Dy": Dy}, transformations=transformations)


def analizar_ecuacion(texto: str):
    """
    Convierte lo que escribió el usuario en:
      - rhs: la expresión tal que dy/dx = rhs
      - M, N: si la ecuación se escribió completa como M + N*dy/dx = 0,
        se devuelven M y N tal como el usuario los escribió (necesario
        para el método de ecuaciones exactas). Si el usuario solo dio
        el lado derecho, M y N son None.
    """
    texto = texto.strip().replace("^", "**")

    if "=" not in texto:
        try:
            rhs = _parse(texto)
        except Exception:
            raise ValueError(
                "No pude leer esa expresión. Revisa que solo uses x, y, "
                "+, -, *, /, ^ y paréntesis. Ejemplo: x*(1+y^2)"
            )
        return rhs, None, None

    texto_proc = texto.replace("dy/dx", "Dy").replace("y'", "Dy")
    if "Dy" not in texto_proc:
        raise ValueError(
            "Tu ecuación tiene un '=' pero no encontré 'dy/dx' ni 'y''. "
            "Escríbela como 'dy/dx + 3*x*y = 6*x', o si prefieres, escribe "
            "solo el lado derecho de dy/dx = ..., por ejemplo: x*y"
        )

    izq_texto, der_texto = texto_proc.split("=", 1)
    try:
        izq = _parse(izq_texto)
        der = _parse(der_texto)
    except Exception:
        raise ValueError(
            "No pude leer esa ecuación. Revisa que solo uses x, y, dy/dx (o "
            "y'), +, -, *, /, ^ y paréntesis."
        )

    diferencia = sp.expand(izq - der)

    if Dy not in diferencia.free_symbols:
        raise ValueError("No encontré dy/dx (o y') en tu ecuación.")

    poly_dy = sp.Poly(diferencia, Dy)
    if poly_dy.degree() != 1:
        raise ValueError("No logré despejar dy/dx de esa ecuación.")

    N_coef, M_coef = poly_dy.all_coeffs()  # diferencia = N_coef*Dy + M_coef
    rhs = sp.simplify(-M_coef / N_coef)
    return rhs, sp.simplify(M_coef), sp.simplify(N_coef)


def _signo(coef_latex: str) -> str:
    """Devuelve '+ x' o '- x' con el signo correcto para insertar en una suma."""
    if coef_latex.startswith("-"):
        return f"- {coef_latex[1:]}"
    return f"+ {coef_latex}"


def construir_separable(rhs):
    try:
        separada = sp.separatevars(rhs, symbols=[x, y], dict=True)
    except Exception:
        return None
    if not separada or x not in separada or y not in separada:
        return None

    h_x = separada[x] * separada.get("coeff", 1)
    g_y = separada[y]

    pasos = [Paso(
        titulo="1. Ecuación original",
        contenido=rf"\frac{{dy}}{{dx}} = {sp.latex(rhs)}"
    )]

    inv_g = sp.together(1 / g_y)
    denom_inv_g = sp.denom(inv_g)
    if denom_inv_g == 1:
        lado_izq_sep = rf"{sp.latex(inv_g)}\,dy"
    else:
        lado_izq_sep = rf"\frac{{dy}}{{{sp.latex(g_y)}}}"

    pasos.append(Paso(
        titulo="2. Separar variables",
        contenido=rf"{lado_izq_sep} = {sp.latex(h_x)}\,dx"
    ))
    pasos.append(Paso(
        titulo="3. Integrar ambos lados",
        contenido=rf"\int {lado_izq_sep} = \int {sp.latex(h_x)}\,dx"
    ))

    try:
        integral_izq = sp.integrate(inv_g, y)
        integral_der = sp.integrate(h_x, x)
    except Exception:
        return None

    pasos.append(Paso(
        titulo="4. Resolver las integrales",
        contenido=rf"{sp.latex(integral_izq)} = {sp.latex(integral_der)} + C"
    ))

    y_explicita = None
    try:
        despejes = sp.solve(sp.Eq(integral_izq, integral_der + C1), y)
        if despejes:
            y_explicita = despejes[0]
    except Exception:
        y_explicita = None

    if y_explicita is not None:
        pasos.append(Paso(titulo="5. Despejar y", contenido=rf"y = {sp.latex(y_explicita)}"))
        solucion_final = rf"y = {sp.latex(y_explicita)}"
    else:
        solucion_final = rf"{sp.latex(integral_izq)} = {sp.latex(integral_der)} + C"

    return Respuesta(tipo="Variables separables", pasos=pasos, solucion=solucion_final)


def construir_lineal(rhs):
    try:
        polinomio = sp.Poly(sp.expand(rhs), y)
    except Exception:
        return None
    if polinomio.degree() > 1:
        return None

    coeffs = polinomio.all_coeffs()
    if polinomio.degree() == 1:
        a1, a0 = coeffs
    else:
        a1, a0 = sp.Integer(0), (coeffs[0] if coeffs else sp.Integer(0))

    if y in a1.free_symbols or y in a0.free_symbols:
        return None

    p_x = sp.simplify(-a1)
    q_x = sp.simplify(a0)

    pasos = [Paso(
        titulo="1. Ecuación original",
        contenido=rf"\frac{{dy}}{{dx}} = {sp.latex(rhs)}"
    )]
    p_latex = sp.latex(p_x)
    forma_estandar = rf"\frac{{dy}}{{dx}} {_signo(p_latex)}\,y = {sp.latex(q_x)}"

    pasos.append(Paso(
        titulo="2. Escribir en forma estándar",
        contenido=forma_estandar
    ))

    try:
        integral_p = sp.integrate(p_x, x)
        mu = sp.simplify(sp.exp(integral_p))
    except Exception:
        return None

    pasos.append(Paso(
        titulo="3. Calcular el factor integrante",
        contenido=rf"\mu(x) = e^{{\int {sp.latex(p_x)}\,dx}} = {sp.latex(mu)}"
    ))

    lado_der_mu = sp.simplify(mu * q_x)
    mu_latex = sp.latex(mu)
    mu_p_latex = sp.latex(sp.simplify(mu * p_x))

    pasos.append(Paso(
        titulo="4. Multiplicar toda la ecuación por μ(x)",
        contenido=rf"{mu_latex}\frac{{dy}}{{dx}} + {mu_p_latex}\,y = {sp.latex(lado_der_mu)}"
    ))

    pasos.append(Paso(
        titulo="5. El lado izquierdo es la derivada de un producto (regla del producto)",
        contenido=rf"\frac{{d}}{{dx}}\big[{mu_latex}\,y\big] = {mu_latex}\frac{{dy}}{{dx}} + {mu_p_latex}\,y"
    ))

    pasos.append(Paso(
        titulo="6. Por eso la ecuación se puede reescribir como",
        contenido=rf"\frac{{d}}{{dx}}\big[{mu_latex}\,y\big] = {sp.latex(lado_der_mu)}"
    ))

    try:
        integral_der = sp.integrate(lado_der_mu, x)
    except Exception:
        return None

    pasos.append(Paso(
        titulo="7. Integrar ambos lados",
        contenido=rf"{mu_latex}\,y = {sp.latex(integral_der)} + C"
    ))

    y_explicita = sp.simplify((integral_der + C1) / mu)
    pasos.append(Paso(titulo="8. Despejar y", contenido=rf"y = {sp.latex(y_explicita)}"))

    return Respuesta(
        tipo="Lineal de primer orden (factor integrante)",
        pasos=pasos,
        solucion=rf"y = {sp.latex(y_explicita)}",
    )


def construir_homogenea(rhs):
    """Ecuaciones homogéneas: dy/dx = f(x,y) con f(tx,ty) = f(x,y). Sustitución y = v x."""
    t = sp.symbols("t", positive=True)
    try:
        es_homogenea = sp.simplify(rhs.subs({x: t * x, y: t * y}, simultaneous=True) - rhs) == 0
    except Exception:
        return None
    if not es_homogenea:
        return None

    v = sp.symbols("v")
    try:
        g_v = sp.simplify(rhs.subs(y, v * x))
    except Exception:
        return None
    if x in g_v.free_symbols:
        return None  # no se canceló bien la x; no tratamos este caso

    pasos = [Paso(
        titulo="1. Ecuación original",
        contenido=rf"\frac{{dy}}{{dx}} = {sp.latex(rhs)}"
    )]
    pasos.append(Paso(
        titulo="2. Es homogénea: al sustituir y = vx, queda en función solo de v",
        contenido=rf"v = \frac{{y}}{{x}} \qquad \Longrightarrow \qquad \frac{{dy}}{{dx}} = {sp.latex(g_v)}"
    ))
    pasos.append(Paso(
        titulo="3. Sustituir y = vx y dy/dx = v + x·dv/dx",
        contenido=rf"v + x\frac{{dv}}{{dx}} = {sp.latex(g_v)}"
    ))

    diff_expr = sp.simplify(g_v - v)
    if diff_expr == 0:
        return None  # y = vx (caso degenerado)

    pasos.append(Paso(
        titulo="4. Despejar y separar variables (v y x)",
        contenido=rf"\frac{{dv}}{{{sp.latex(diff_expr)}}} = \frac{{dx}}{{x}}"
    ))

    try:
        integral_v = sp.integrate(1 / diff_expr, v)
        integral_x = sp.integrate(1 / x, x)
    except Exception:
        return None

    pasos.append(Paso(
        titulo="5. Integrar ambos lados",
        contenido=rf"{sp.latex(integral_v)} = {sp.latex(integral_x)} + C"
    ))

    final_izq = sp.simplify(integral_v.subs(v, y / x))
    pasos.append(Paso(
        titulo="6. Sustituir de vuelta v = y/x",
        contenido=rf"{sp.latex(final_izq)} = {sp.latex(integral_x)} + C"
    ))

    y_explicita = None
    try:
        despejes = sp.solve(sp.Eq(final_izq, integral_x + C1), y)
        if despejes:
            y_explicita = despejes[0]
    except Exception:
        y_explicita = None

    if y_explicita is not None:
        pasos.append(Paso(titulo="7. Despejar y", contenido=rf"y = {sp.latex(y_explicita)}"))
        solucion_final = rf"y = {sp.latex(y_explicita)}"
    else:
        solucion_final = rf"{sp.latex(final_izq)} = {sp.latex(integral_x)} + C"

    return Respuesta(tipo="Homogénea (sustitución y = vx)", pasos=pasos, solucion=solucion_final)


def construir_bernoulli(rhs):
    """Bernoulli: dy/dx + p(x) y = q(x) y^n, con n != 0, 1. Sustitución v = y^(1-n)."""
    p_w = sp.Wild("p", exclude=[y])
    q_w = sp.Wild("q", exclude=[y])
    n_w = sp.Wild("n", exclude=[x, y])

    matched = sp.expand(rhs).match(-p_w * y + q_w * y ** n_w)
    if not matched:
        return None
    p_x, q_x, n_val = matched.get(p_w), matched.get(q_w), matched.get(n_w)
    if p_x is None or q_x is None or n_val is None:
        return None
    if n_val in (0, 1) or not n_val.is_number:
        return None
    if y in p_x.free_symbols or y in q_x.free_symbols:
        return None

    uno_menos_n = 1 - n_val

    pasos = [Paso(
        titulo="1. Ecuación original",
        contenido=rf"\frac{{dy}}{{dx}} = {sp.latex(rhs)}"
    )]
    pasos.append(Paso(
        titulo="2. Escribir en forma estándar de Bernoulli",
        contenido=rf"\frac{{dy}}{{dx}} {_signo(sp.latex(p_x))}\,y = {sp.latex(q_x)}\,y^{{{sp.latex(n_val)}}}"
    ))
    pasos.append(Paso(
        titulo=rf"3. Dividir toda la ecuación entre y^{sp.latex(n_val)}",
        contenido=rf"y^{{{sp.latex(-n_val)}}}\frac{{dy}}{{dx}} {_signo(sp.latex(p_x))}\,y^{{{sp.latex(uno_menos_n)}}} = {sp.latex(q_x)}"
    ))
    pasos.append(Paso(
        titulo="4. Sustituir v = y^(1−n), de donde dv/dx = (1−n)·y^(−n)·dy/dx",
        contenido=rf"v = y^{{{sp.latex(uno_menos_n)}}} \qquad \Longrightarrow \qquad "
                  rf"\frac{{dv}}{{dx}} = ({sp.latex(uno_menos_n)})\,y^{{{sp.latex(-n_val)}}}\frac{{dy}}{{dx}}"
    ))

    p_v = sp.simplify(uno_menos_n * p_x)
    q_v = sp.simplify(uno_menos_n * q_x)
    pasos.append(Paso(
        titulo="5. La ecuación se convierte en una ecuación lineal, pero en v",
        contenido=rf"\frac{{dv}}{{dx}} {_signo(sp.latex(p_v))}\,v = {sp.latex(q_v)}"
    ))

    try:
        integral_pv = sp.integrate(p_v, x)
        mu = sp.simplify(sp.exp(integral_pv))
    except Exception:
        return None

    pasos.append(Paso(
        titulo="6. Calcular el factor integrante (para v)",
        contenido=rf"\mu(x) = e^{{\int {sp.latex(p_v)}\,dx}} = {sp.latex(mu)}"
    ))

    lado_der_mu = sp.simplify(mu * q_v)
    try:
        integral_der = sp.integrate(lado_der_mu, x)
    except Exception:
        return None

    pasos.append(Paso(
        titulo="7. Multiplicar por μ(x) e integrar (igual que en el método lineal)",
        contenido=rf"{sp.latex(mu)}\,v = {sp.latex(integral_der)} + C"
    ))

    v_explicita = sp.simplify((integral_der + C1) / mu)
    pasos.append(Paso(titulo="8. Despejar v", contenido=rf"v = {sp.latex(v_explicita)}"))

    exponente_final = sp.nsimplify(1 / uno_menos_n)
    y_explicita = sp.simplify(v_explicita ** exponente_final)
    pasos.append(Paso(
        titulo="9. Sustituir de vuelta v = y^(1−n) y despejar y",
        contenido=rf"y = \left({sp.latex(v_explicita)}\right)^{{{sp.latex(exponente_final)}}}"
    ))

    return Respuesta(
        tipo="Bernoulli (sustitución v = y¹⁻ⁿ)",
        pasos=pasos,
        solucion=rf"y = \left({sp.latex(v_explicita)}\right)^{{{sp.latex(exponente_final)}}}",
    )


def construir_exacta(M, N):
    """Ecuaciones exactas: M(x,y) dx + N(x,y) dy = 0, con ∂M/∂y = ∂N/∂x."""
    if M is None or N is None:
        return None
    try:
        dM_dy = sp.simplify(sp.diff(M, y))
        dN_dx = sp.simplify(sp.diff(N, x))
    except Exception:
        return None
    if sp.simplify(dM_dy - dN_dx) != 0:
        return None

    pasos = [Paso(
        titulo="1. Escribir en la forma M dx + N dy = 0",
        contenido=rf"\big({sp.latex(M)}\big)\,dx + \big({sp.latex(N)}\big)\,dy = 0"
    )]
    pasos.append(Paso(
        titulo="2. Verificar exactitud: ∂M/∂y debe ser igual a ∂N/∂x",
        contenido=rf"\frac{{\partial M}}{{\partial y}} = {sp.latex(dM_dy)} "
                  rf"\qquad \frac{{\partial N}}{{\partial x}} = {sp.latex(dN_dx)} \quad \checkmark"
    ))

    try:
        Fx = sp.integrate(M, x)
    except Exception:
        return None
    pasos.append(Paso(
        titulo="3. Integrar M respecto a x (tratando a y como constante)",
        contenido=rf"F(x,y) = \int {sp.latex(M)}\,dx = {sp.latex(Fx)} + h(y)"
    ))

    dFx_dy = sp.diff(Fx, y)
    h_prima = sp.simplify(N - dFx_dy)
    pasos.append(Paso(
        titulo="4. Derivar F respecto a y e igualar con N, para hallar h'(y)",
        contenido=rf"\frac{{\partial F}}{{\partial y}} = {sp.latex(dFx_dy)} + h'(y) = {sp.latex(N)} "
                  rf"\;\Longrightarrow\; h'(y) = {sp.latex(h_prima)}"
    ))

    try:
        h = sp.integrate(h_prima, y)
    except Exception:
        return None
    pasos.append(Paso(titulo="5. Integrar para obtener h(y)", contenido=rf"h(y) = {sp.latex(h)}"))

    F_final = sp.simplify(Fx + h)
    pasos.append(Paso(
        titulo="6. La solución general queda de forma implícita: F(x,y) = C",
        contenido=rf"{sp.latex(F_final)} = C"
    ))

    return Respuesta(tipo="Exacta", pasos=pasos, solucion=rf"{sp.latex(F_final)} = C")


@app.post("/resolver", response_model=Respuesta)
def resolver(solicitud: Solicitud):
    try:
        rhs, M, N = analizar_ecuacion(solicitud.ecuacion)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="No pude leer esa ecuación. Revisa el formato e intenta de nuevo.",
        )

    metodos = {
        "separable": (lambda: construir_separable(rhs),
                      "Esta ecuación no es de variables separables."),
        "lineal": (lambda: construir_lineal(rhs),
                   "Esta ecuación no es lineal de primer orden (no se puede "
                   "escribir como dy/dx + p(x)·y = q(x))."),
        "homogenea": (lambda: construir_homogenea(rhs),
                      "Esta ecuación no es homogénea (no se puede escribir "
                      "como una función de y/x)."),
        "bernoulli": (lambda: construir_bernoulli(rhs),
                      "Esta ecuación no tiene la forma de Bernoulli "
                      "(dy/dx + p(x)·y = q(x)·yⁿ)."),
        "exacta": (lambda: construir_exacta(M, N),
                   "Esta ecuación no es exacta, o necesitas escribirla "
                   "completa en la forma M + N·dy/dx = 0 (por ejemplo: "
                   "2*x*y + (x^2+3*y^2)*dy/dx = 0) para poder verificarlo."),
    }

    if solicitud.metodo in metodos:
        construir, mensaje_error = metodos[solicitud.metodo]
        resultado = construir()
        if resultado is not None:
            return resultado
        raise HTTPException(status_code=422, detail=mensaje_error + " Prueba con 'Automático'.")

    # modo "auto": prueba los métodos en orden, del más simple al más general
    for nombre in ("separable", "lineal", "homogenea", "bernoulli", "exacta"):
        construir, _ = metodos[nombre]
        resultado = construir()
        if resultado is not None:
            return resultado

    raise HTTPException(
        status_code=422,
        detail="Esta ecuación no coincide con ninguno de los tipos que "
               "soporta este prototipo (separables, lineales, homogéneas, "
               "Bernoulli o exactas). Si crees que debería ser 'exacta', "
               "asegúrate de escribir la ecuación completa como "
               "M + N·dy/dx = 0.",
    )

# Sirve el frontend (static/index.html) en la raíz "/"
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
