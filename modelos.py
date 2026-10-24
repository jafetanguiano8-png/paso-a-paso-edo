"""Modelos de datos compartidos por los distintos módulos de la app."""

from pydantic import BaseModel


class Paso(BaseModel):
    titulo: str
    contenido: str  # LaTeX


class Respuesta(BaseModel):
    tipo: str
    pasos: list[Paso]
    solucion: str
