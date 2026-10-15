import pytest

from app.perfiles_prueba import perfiles_prueba
from app.recomendador import cargar_lugares


@pytest.fixture(scope="session")
def lugares():
    return cargar_lugares()


@pytest.fixture(scope="session")
def perfiles():
    return perfiles_prueba()
