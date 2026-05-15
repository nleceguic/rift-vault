"""
hooks/ – Sistema de extensión por hooks.

Para añadir un hook:
    1. Crear una clase que herede de BaseHook
    2. Sobrescribir los métodos que necesites
    3. Registrarla en main.py: HooksRegistry.instance().register(MyHook())
"""
from app.hooks.base_hook       import BaseHook
from app.hooks.hooks_registry  import HooksRegistry

__all__ = ["BaseHook", "HooksRegistry"]
