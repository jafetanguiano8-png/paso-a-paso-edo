"""
Ecuaciones diferenciales lineales de orden superior con coeficientes constantes.

Etapa 1: homogéneas  a_n y^(n) + ... + a_1 y' + a_0 y = 0
         usando el operador D y la ecuación característica.

Formatos de entrada aceptados (se pueden mezclar):
    y'' - 3*y' + 2*y = 0
    y''' - y'' - 4*y' + 4*y = 0
    d2y/dx2 + 4*y = 0
    (D^2 - 3*D + 2)*y = 0
    (D - 1)*(D - 2)*y = 0
"""

import re

import sympy as sp
from fastapi import HTTPException
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from modelos import Paso, Respuesta

x = sp.symbols("x")
D = sp.symbols("D")
m = sp.symbols("m")
Y0 = sp.symbols("Y_0")
_DERIVADAS = {k: sp.symbols(f"Y_{k}") for k in range(1, 9)}

_TRANSFORMACIONES = standard_transformations + (implicit_multiplication_application,)

# Detecta: y'' (o más primas), d2y/dx2, o la letra D (operador) sola
_PATRON_ORDEN_SUPERIOR = re.compile(r"y''|d\dy/dx\d|y\^\(\d+\)|(?<![A-Za-z])D(?:[^A-Za-z]|y|$)")

METODOS_PRIMER_ORDEN = {"separable", "lineal", "homogenea", "bernoulli", "exacta"}


def es_orden_superior(texto: str) -> bool:
    return bool(_PATRON_ORDEN_SUPERIOR.search(texto))


# ---------------------------------------------------------------- lectura

def _normalizar(texto: str) -> str:
    t = texto.strip().replace("^", "**").replace("’", "'").replace("′", "'")
    t = re.sub(r"y\*\*\((\d+)\)", lambda mo: f"Y_{mo.group(1)}", t)  # y^(4)
    t = re.sub(r"d(\d)y/dx\1", lambda mo: f"Y_{mo.group(1)}", t)
    t = t.replace("dy/dx", "Y_1")
    t = re.sub(r"y('+)", lambda mo: f"Y_{len(mo.group(1))}", t)
    return t


def _parse(texto: str):
    local = {"x": x, "D": D, "y": Y0, "Y_0": Y0}
    local.update({f"Y_{k}": s for k, s in _DERIVADAS.items()})
    return parse_expr(texto, local_dict=local, transformations=_TRANSFORMACIONES)


def analizar_orden_superior(texto: str):
    """
    Devuelve (orden, coefs, g): coefs son los coeficientes del polinomio en D
    (de mayor a menor grado) y g es el lado derecho, de modo que P(D) y = g.
    """
    t = _normalizar(texto)
    if "=" not in t:
        raise ValueError(
            "Escribe la ecuación completa con el signo '=', por ejemplo: "
            "y'' - 3*y' + 2*y = 0  ó  (D^2 - 3*D + 2)*y = 0"
        )

    izq_txt, der_txt = t.split("=", 1)
    try:
        izq, der = _parse(izq_txt), _parse(der_txt)
    except Exception:
        raise ValueError(
            "No pude leer esa ecuación. Usa y, y', y'', ... (o el operador D), "
            "x, números, + - * / ^ y paréntesis. Ejemplo: y'' + 2*y' + 5*y = 0"
        )

    sustituciones = {s: D**k * Y0 for k, s in _DERIVADAS.items()}
    expr = sp.expand((izq - der).subs(sustituciones))

    extra = expr.free_symbols - {x, D, Y0}
    if extra:
        raise ValueError("Solo puedo usar las letras x, y y D en la ecuación.")

    try:
        poly_y = sp.Poly(expr, Y0)
    except Exception:
        raise ValueError("La ecuación debe ser lineal en y y sus derivadas.")

    if poly_y.degree() != 1:
        raise ValueError(
            "La ecuación debe ser lineal en y y sus derivadas (sin productos "
            "entre y y sus derivadas ni funciones de y)."
        )

    c1, c0 = poly_y.all_coeffs()
    g = sp.simplify(-c0)

    try:
        poly_D = sp.Poly(sp.expand(c1), D)
    except Exception:
        raise ValueError("No pude interpretar los coeficientes de la ecuación.")

    coefs = poly_D.all_coeffs()
    if any(c.free_symbols for c in coefs):
        raise ValueError(
            "Por ahora solo resuelvo ecuaciones con coeficientes constantes "
            "(números, no funciones de x)."
        )
    if poly_D.degree() < 1:
        raise ValueError("No encontré derivadas de y en la ecuación.")

    return poly_D.degree(), coefs, g


# ------------------------------------------------------------ utilidades LaTeX

def _y_latex(k: int) -> str:
    if k == 0:
        return "y"
    if k <= 3:
        return "y" + "'" * k
    return rf"y^{{({k})}}"


def _base_potencia(simbolo: str):
    def base(k: int) -> str:
        if k == 0:
            return ""
        if k == 1:
            return simbolo
        return rf"{simbolo}^{{{k}}}"

    return base


def _suma_latex(coefs, base) -> str:
    """Escribe a_n*base(n) + ... + a_0*base(0) con los signos bien puestos."""
    orden = len(coefs) - 1
    salida = ""
    primero = True
    for i, c in enumerate(coefs):
        if c == 0:
            continue
        k = orden - i
        b = base(k)
        c_abs = abs(c)
        if b == "":
            cuerpo = sp.latex(c_abs)
        elif c_abs == 1:
            cuerpo = b
        else:
            cuerpo = sp.latex(c_abs) + b
        if primero:
            salida += ("-" if c < 0 else "") + cuerpo
            primero = False
        else:
            salida += (" - " if c < 0 else " + ") + cuerpo
    return salida


def _lineas(lineas) -> str:
    return r"\begin{aligned}" + r" \\ ".join(lineas) + r"\end{aligned}"


def _suma_constantes(bases) -> str:
    terminos = []
    for i, b in enumerate(bases, start=1):
        c = rf"C_{{{i}}}"
        terminos.append(c if b == 1 else c + r"\," + sp.latex(b))
    return " + ".join(terminos)


# ------------------------------------------------------------------ solución

def _raices_con_multiplicidad(coefs):
    polinomio = sp.Poly(sum(c * m**(len(coefs) - 1 - i) for i, c in enumerate(coefs)), m)
    raices = sp.roots(polinomio)
    if sum(raices.values()) != polinomio.degree():
        return None
    return polinomio, raices


def _es_real(r) -> bool:
    return sp.simplify(sp.im(r)) == 0


def construir_homogenea_constantes(orden, coefs):
    pasos = []

    # 1. Ecuación original
    pasos.append(Paso(
        titulo="1. Ecuación original",
        contenido=rf"{_suma_latex(coefs, _y_latex)} = 0",
    ))

    # 2. Operador D
    pasos.append(Paso(
        titulo="2. Reescribir con el operador diferencial D (D = d/dx)",
        contenido=rf"\left({_suma_latex(coefs, _base_potencia('D'))}\right)y = 0",
    ))

    # 3. Ecuación característica
    pasos.append(Paso(
        titulo="3. Ecuación característica: cambiar D por m",
        contenido=rf"{_suma_latex(coefs, _base_potencia('m'))} = 0",
    ))

    encontradas = _raices_con_multiplicidad(coefs)
    if encontradas is None:
        return None
    polinomio, raices = encontradas

    # Discriminante (solo cuando la ecuación característica es cuadrática)
    if orden == 2:
        a, b, c = coefs
        disc = sp.simplify(b**2 - 4 * a * c)
        if disc > 0:
            caso = r"\Delta > 0 \;\Rightarrow\; \text{dos raíces reales distintas}"
        elif disc == 0:
            caso = r"\Delta = 0 \;\Rightarrow\; \text{una raíz real repetida}"
        else:
            caso = r"\Delta < 0 \;\Rightarrow\; \text{dos raíces complejas conjugadas}"
        pasos.append(Paso(
            titulo="4. Calcular el discriminante: define cuál de los tres casos es",
            contenido=rf"\Delta = b^2 - 4ac = ({sp.latex(b)})^2 - 4({sp.latex(a)})({sp.latex(c)}) "
                      rf"= {sp.latex(disc)} \qquad {caso}",
        ))
        n_paso = 5
    else:
        n_paso = 4

    # Factorizar y listar raíces
    todas = []
    for r, k in raices.items():
        todas.extend([r] * k)
    try:
        todas.sort(key=lambda r: (float(sp.re(sp.N(r))), float(sp.im(sp.N(r)))))
    except Exception:
        pass
    lista_raices = r",\; ".join(rf"m_{{{i}}} = {sp.latex(r)}" for i, r in enumerate(todas, start=1))
    factorizada = sp.factor(polinomio.as_expr(), m)
    pasos.append(Paso(
        titulo=f"{n_paso}. Resolver la ecuación característica (factorizar y hallar las raíces)",
        contenido=rf"{sp.latex(factorizada)} = 0 \qquad \Rightarrow \qquad {lista_raices}",
    ))
    n_paso += 1

    # Clasificar las raíces
    simples, repetidas, complejas = [], [], []
    for r, k in raices.items():
        if _es_real(r):
            (simples if k == 1 else repetidas).append((r, k))
        elif sp.simplify(sp.im(r)) > 0:
            complejas.append((r, k))
    key = lambda par: float(sp.N(sp.re(par[0])))
    simples.sort(key=key)
    repetidas.sort(key=key)
    complejas.sort(key=key)

    bases = []

    if simples:
        lineas = []
        for r, _ in simples:
            f = sp.exp(r * x)
            bases.append(f)
            lineas.append(rf"m = {sp.latex(r)} \;\Rightarrow\; {sp.latex(f)}")
        pasos.append(Paso(
            titulo=f"{n_paso}. Caso 1 — raíces reales distintas: cada raíz m aporta e^(m·x)",
            contenido=_lineas(lineas),
        ))
        n_paso += 1

    if repetidas:
        lineas = []
        for r, k in repetidas:
            fs = [x**j * sp.exp(r * x) for j in range(k)]
            bases.extend(fs)
            lineas.append(
                rf"m = {sp.latex(r)} \text{{ (multiplicidad }} {k} \text{{)}} \;\Rightarrow\; "
                + r",\; ".join(sp.latex(f) for f in fs)
            )
        pasos.append(Paso(
            titulo=f"{n_paso}. Caso 2 — raíces reales repetidas: multiplicidad k aporta e^(m·x), x·e^(m·x), ..., x^(k-1)·e^(m·x)",
            contenido=_lineas(lineas),
        ))
        n_paso += 1

    if complejas:
        lineas = []
        for r, k in complejas:
            alfa, beta = sp.simplify(sp.re(r)), sp.simplify(sp.im(r))
            fs = []
            for j in range(k):
                fs.append(x**j * sp.exp(alfa * x) * sp.cos(beta * x))
                fs.append(x**j * sp.exp(alfa * x) * sp.sin(beta * x))
            bases.extend(fs)
            lineas.append(
                rf"m = {sp.latex(alfa)} \pm {sp.latex(beta)}\,i \;\Rightarrow\; "
                rf"\alpha = {sp.latex(alfa)},\; \beta = {sp.latex(beta)} \;\Rightarrow\; "
                + r",\; ".join(sp.latex(f) for f in fs)
            )
        pasos.append(Paso(
            titulo=f"{n_paso}. Caso 3 — raíces complejas conjugadas α ± βi: aportan e^(α·x)·cos(β·x) y e^(α·x)·sen(β·x)",
            contenido=_lineas(lineas),
        ))
        n_paso += 1

    # Solución general
    suma = _suma_constantes(bases)
    pasos.append(Paso(
        titulo=f"{n_paso}. Solución general: combinación lineal de las soluciones base",
        contenido=rf"y(x) = {suma}",
    ))
    n_paso += 1

    # Verificación con SymPy
    constantes = sp.symbols(f"C_1:{len(bases) + 1}")
    y_gen = sum(c * f for c, f in zip(constantes, bases))
    residuo = sum(c * sp.diff(y_gen, x, orden - i) for i, c in enumerate(coefs))
    try:
        ok = sp.simplify(sp.expand(residuo)) == 0
    except Exception:
        ok = False
    if ok:
        pasos.append(Paso(
            titulo=f"{n_paso}. Verificación con SymPy: al sustituir y(x) y sus derivadas en la ecuación se obtiene 0",
            contenido=rf"\left({_suma_latex(coefs, _base_potencia('D'))}\right)y(x) = 0 \;\checkmark",
        ))

    return Respuesta(
        tipo=f"Orden {orden} · homogénea de coeficientes constantes",
        pasos=pasos,
        solucion=rf"y(x) = {suma}",
    )


# ------------------------------------------------------------- punto de entrada

def resolver_orden_superior(texto: str, metodo: str = "auto") -> Respuesta:
    if metodo in METODOS_PRIMER_ORDEN:
        raise HTTPException(
            status_code=422,
            detail="Ese método es para ecuaciones de primer orden. Para esta "
                   "ecuación de orden superior elige 'Automático'.",
        )

    try:
        orden, coefs, g = analizar_orden_superior(texto)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if g != 0:
        raise HTTPException(
            status_code=422,
            detail="Esta ecuación es no homogénea (el lado derecho no es 0). "
                   "Los métodos de coeficientes indeterminados y variación de "
                   "parámetros se agregarán en las siguientes etapas. Por "
                   "ahora puedes resolver su ecuación homogénea asociada "
                   "escribiendo = 0.",
        )

    resultado = construir_homogenea_constantes(orden, coefs)
    if resultado is None:
        raise HTTPException(
            status_code=422,
            detail="No pude encontrar las raíces exactas de la ecuación "
                   "característica de esta ecuación.",
        )
    return resultado
