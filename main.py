"""
main.py – Punto de entrada de Rift Vault.

Para añadir hooks o servicios extra al arrancar:
    HooksRegistry.instance().register(MyHook())
    registry.register_extra(SyncService(...))
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.error_handler import setup_logging

# Logging debe configurarse antes de importar cualquier otro módulo de la app
setup_logging()

import logging
logger = logging.getLogger(__name__)


def main():
    from app.core.service_registry import ServiceRegistry
    from app.core.error_handler    import ErrorHandler
    from app.ui.app_window         import AppWindow

    logger.info("Arrancando Rift Vault...")

    registry = ServiceRegistry().build()
    logger.info("ServiceRegistry listo.")

    app = AppWindow(registry=registry)

    # Instalar gestión global de errores una vez que la ventana existe
    ErrorHandler().install(app)
    logger.info("ErrorHandler instalado.")

    app.mainloop()
    logger.info("Aplicación cerrada.")


if __name__ == "__main__":
    main()
