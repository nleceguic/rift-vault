# Rift Vault

**Gestor seguro de cuentas de League of Legends para Windows 11.**

Rift Vault almacena, organiza y protege tus credenciales de LoL con cifrado de nivel producción, sin dependencias de la nube y con protecciones específicamente pensadas para el contexto gaming (streaming, multi-account, acceso físico compartido).

---

## Características

### Gestión de cuentas
- Crear, editar y eliminar cuentas con alias, username, contraseña, región, tags, notas y Riot ID
- 11 regiones soportadas: EUW, EUNE, NA, LAS, LAN, BR, OCE, KR, JP, TR, RU
- Búsqueda full-text en alias, username, notas y tags con operadores avanzados (`tag:`, `region:`, `"frase exacta"`, `-exclusión`)
- Filtrado por región y tags con lógica AND
- Ordenación por alias (A-Z / Z-A) y por fecha (más reciente / más antiguo)
- Autocompletado de tags al crear y editar cuentas

### Portapapeles seguro
- Copia de usuario, contraseña o ambos con un clic
- TTL de 30 segundos con cuenta atrás visible en el botón
- Limpieza automática del portapapeles al expirar el timer
- Advertencia bloqueante al intentar cerrar con contraseña en portapapeles

### Generador de contraseñas
- Longitud configurable de 8 a 64 caracteres (slider)
- Opciones: mayúsculas, números, símbolos, evitar ambiguos
- Barra de fortaleza con nivel y entropía en bits
- Botón "Usar contraseña" que inserta directamente en el formulario

### Historial de contraseñas
- Registro automático de cada cambio de contraseña con timestamp
- Modal de historial con contraseñas enmascaradas y toggle mostrar/ocultar
- Las contraseñas del historial se cifran con la misma clave maestra

### Lanzador integrado
- Detecta automáticamente `RiotClientServices.exe` o `LeagueClient.exe`
- Búsqueda en rutas comunes (`C:/`, `D:/`, `E:/`), variables de entorno y registro de Windows
- Ruta personalizable en Ajustes → Lanzador con botón de explorador
- Diálogo de lanzamiento rápido con copia de usuario y contraseña

### Integración Riot API
- Muestra nivel de invocador, rango y estado de cuenta en cada tarjeta
- Caché local por cuenta para minimizar llamadas a la API
- Configuración de API key en Ajustes con toggle mostrar/ocultar
- Botón de actualización individual por tarjeta

### Exportar / Importar
- **JSON v1** — cifrado con la contraseña maestra actual (mismo dispositivo)
- **JSON v2** — cifrado con contraseña personalizada (portable entre instalaciones)
- **CSV** — texto plano con advertencia explícita (para migración a otros gestores)
- Importación con detección automática de formato, resumen previo y validación de duplicados

### Seguridad
| Mecanismo | Detalle |
|---|---|
| KDF | PBKDF2-HMAC-SHA256, 480 000 iteraciones (OWASP 2024) |
| Cifrado de credenciales | Fernet — AES-128-CBC + HMAC-SHA256 |
| Verificación de contraseña maestra | Canary Fernet cifrado (sin hash expuesto en disco) |
| Integridad del almacenamiento | SQLite con cifrado Fernet por campo; HMAC embebido en exportaciones JSON |
| Contraseñas en memoria | Nunca en texto plano — descifrado on-demand al copiar o ver historial |
| Bloqueo por inactividad | Auto-lock configurable (5 / 10 / 15 / 30 / 60 min) con overlay de re-autenticación |
| Protección contra screen scrapers | `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` — la ventana aparece negra en OBS y software de grabación mientras hay una contraseña en el portapapeles |
| Rate limiting | Delays crecientes (2 s → 5 s → 15 s) tras intentos fallidos de desbloqueo |
| Escritura atómica | `.tmp` + `os.replace()` — sin corrupción ante fallos de disco |
| Cambio de contraseña maestra | Re-cifrado de todas las credenciales sin exponer texto plano en disco |

### UX
- Tema oscuro inspirado en League of Legends (dorado `#C89B3C`, azul noche `#0D0D14`)
- Soporte completo de tema Sistema / Claro / Oscuro con detección automática del SO
- Animación escalonada de tarjetas al cargar
- Toggle mostrar / ocultar contraseña en formularios e historial
- Indicador "Protección activa" en sidebar al copiar contraseñas
- Estado vacío contextual según búsqueda activa o sin cuentas
- Tooltips en todos los botones de acción
- Formulario de cuenta con scroll para adaptarse a cualquier resolución y DPI

---

## Instalación

```bash
# 1. Clonar o descargar
cd rift_vault

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar
python main.py
```

**Requisitos:** Python 3.11+, Windows 10 (build 19041+) o Windows 11.

> La protección contra screen scrapers (`SetWindowDisplayAffinity`) requiere Windows 10 versión 2004 o superior. En versiones anteriores la app funciona con normalidad, pero sin esa protección.

---

## Estructura del proyecto

```
rift_vault/
├── main.py                              # Punto de entrada
├── requirements.txt
└── app/
    ├── config.py                        # Constantes globales, paleta de colores y fuentes
    ├── core/
    │   ├── account.py                   # Modelo de dominio (dataclass Account)
    │   ├── account_service.py           # Lógica de negocio, validación y CRUD
    │   ├── crypto_service.py            # PBKDF2 + Fernet + firma HMAC de exportaciones
    │   ├── event_bus.py                 # Pub/sub para comunicación entre capas
    │   ├── service_registry.py          # Contenedor de inyección de dependencias
    │   ├── settings_service.py          # Persistencia de preferencias de usuario
    │   ├── password_generator.py        # Generación segura + evaluación de fortaleza
    │   ├── password_history_service.py  # Historial de contraseñas por cuenta
    │   ├── export_service.py            # Exportar / importar JSON v1, JSON v2 y CSV
    │   ├── advanced_search.py           # Motor de búsqueda con operadores
    │   ├── riot_api_service.py          # Integración Riot Games API
    │   ├── launcher_service.py          # Detección y lanzamiento del cliente de LoL
    │   ├── error_handler.py             # Manejo de errores global
    │   └── win32_utils.py               # API Windows (protección contra capturas)
    ├── storage/
    │   ├── base_storage.py              # Interfaz abstracta del repositorio
    │   ├── sqlite_storage.py            # Persistencia SQLite con cifrado por campo (principal)
    │   └── json_storage.py              # Persistencia JSON heredada (migración automática)
    ├── hooks/
    │   ├── base_hook.py                 # Interfaz de extensión
    │   └── hooks_registry.py            # Registro de hooks (extensibilidad activa)
    └── ui/
        ├── app_window.py                # Ventana raíz, timer de inactividad, navegación
        ├── views/
        │   ├── unlock_view.py           # Login / configuración inicial
        │   ├── home_view.py             # Dashboard con estadísticas
        │   ├── accounts_view.py         # Lista y gestión de cuentas
        │   └── settings_view.py         # Ajustes (Seguridad, Apariencia, Riot API, Lanzador, Datos)
        └── components/
            ├── account_card.py          # Tarjeta individual con copiar, editar, historial y lanzar
            ├── account_form_dialog.py   # Modal crear / editar con scroll
            ├── filter_bar.py            # Búsqueda avanzada, filtros y ordenación
            ├── lock_overlay.py          # Pantalla de bloqueo por inactividad
            ├── change_password_dialog.py       # Cambio de contraseña maestra
            ├── password_generator_dialog.py    # Generador con barra de fortaleza
            ├── password_history_dialog.py      # Historial de contraseñas anteriores
            ├── launch_dialog.py                # Lanzador rápido con copia de credenciales
            ├── tag_autocomplete.py             # Autocompletado de tags
            └── tooltip.py
```

---

## Datos almacenados

Los datos se guardan en `~/.rift_vault/` (carpeta de usuario):

| Archivo | Contenido |
|---|---|
| `master.key` | Salt + canary Fernet cifrado para verificar la contraseña maestra |
| `vault.db` | Base de datos SQLite con cuentas, historial de contraseñas y caché de Riot API |
| `settings.json` | Preferencias de UI (tema, timeout, Riot API key, ruta del lanzador) |

La contraseña maestra **nunca** se almacena — solo el salt y el token de verificación. Cada campo sensible en la base de datos está cifrado individualmente con Fernet. Si se detecta una cuenta migrada desde `accounts.json`, la migración a SQLite se realiza automáticamente en el primer arranque.

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| UI | CustomTkinter 5.2.2 |
| Cifrado | cryptography 48.0.0 (Fernet / PBKDF2) |
| Base de datos | SQLite 3 (stdlib) |
| Imágenes | Pillow 12.2.0 |
| Detección de tema | darkdetect 0.8.0 |
| API de Windows | ctypes (stdlib) |
| Riot API | requests |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                      UI Layer                       │
│  AppWindow · Views · Components · Dialogs           │
└──────────────────────────┬──────────────────────────┘
                           │ EventBus / callbacks
┌──────────────────────────▼──────────────────────────┐
│                  Business Logic                     │
│  AccountService · PasswordHistoryService            │
│  ExportService · RiotApiService · LauncherService   │
│  PasswordGenerator · SettingsService                │
└──────────────────────────┬──────────────────────────┘
                           │ Repository pattern
┌──────────────────────────▼──────────────────────────┐
│                  Storage Layer                      │
│  BaseStorage (ABC) · SqliteStorage · JsonStorage    │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                  Security Layer                     │
│  CryptoService · win32_utils                        │
└─────────────────────────────────────────────────────┘
```

**Patrones implementados:** Layered Architecture, Repository, Dependency Injection (ServiceRegistry), Pub/Sub (EventBus), Hook System.

---

## Tests

```bash
pytest
```

423 tests que cubren servicios de dominio, almacenamiento, cifrado, búsqueda avanzada, generador de contraseñas, exportación/importación, Riot API y lanzador.
