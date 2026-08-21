<div align="center">

# Rift Vault

<img src="logo.png" alt="Rift Vault" width="120"/>

**Secure League of Legends account manager for Windows.**

[![CI](https://github.com/nleceguic/rift-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/nleceguic/rift-vault/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-1f538d)](https://github.com/TomSchimansky/CustomTkinter)
[![License](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)

</div>

## Índice

- [Screenshots](#screenshots)
- [Features](#features)
  - [Security](#security)
  - [Modelo de amenaza](#modelo-de-amenaza)
- [Getting Started](#getting-started)
- [Data Storage](#data-storage)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tests](#tests)
- [License](#license)

---

Rift Vault stores, organizes, and protects your LoL credentials with production-grade encryption — no cloud dependencies, no third-party services. Built with gaming-specific protections in mind: screen capture shielding for streamers, multi-account workflows, and shared physical access scenarios.

---

## Screenshots

> **TODO:** replace each placeholder below with a real screenshot (PNG, ~1280px wide) saved under `screenshots/` with the exact filename shown. Use the light or dark theme consistently across all of them, and blur/replace any real account data with sample values before committing.

<!-- TODO screenshot: unlock_view.py — master password entry screen with the unlock spinner -->
![Unlock screen](screenshots/unlock.png "Unlock screen — capture app/ui/views/unlock_view.py showing the master password field and unlock button (or the spinner mid-unlock)")
**Unlock screen** — master password entry / first-run setup.

<!-- TODO screenshot: home_view.py — dashboard with account stats -->
![Dashboard](screenshots/home.png "Dashboard — capture app/ui/views/home_view.py with a handful of sample accounts so the stats are non-zero")
**Dashboard** — overview stats after unlocking.

<!-- TODO screenshot: accounts_view.py + filter_bar.py + account_card.py — account list -->
![Accounts list](screenshots/accounts.png "Accounts list — capture app/ui/views/accounts_view.py with several account cards visible and the filter bar (app/ui/components/filter_bar.py) at the top, ideally with a search/tag filter active")
**Accounts list** — cards with search, filters, and sorting.

<!-- TODO screenshot: account_form_dialog.py — create/edit account modal -->
![Create/edit account](screenshots/account_form.png "Create/edit account — capture app/ui/components/account_form_dialog.py open with sample (non-real) data filled in")
**Account form** — create/edit modal with alias, region, tags, and notes.

<!-- TODO screenshot: password_generator_dialog.py — generator with strength bar -->
![Password generator](screenshots/password_generator.png "Password generator — capture app/ui/components/password_generator_dialog.py with the length slider, options, and strength/entropy bar visible")
**Password generator** — configurable length, strength bar, entropy.

<!-- TODO screenshot: password_history_dialog.py — masked history list -->
![Password history](screenshots/password_history.png "Password history — capture app/ui/components/password_history_dialog.py with a few masked entries and the show/hide toggle")
**Password history** — timestamped log with masked passwords.

<!-- TODO screenshot: launch_dialog.py — quick-launch with credential copy -->
![Quick launch](screenshots/launch_dialog.png "Quick launch — capture app/ui/components/launch_dialog.py showing the detected client path and one-click copy buttons")
**Quick launch** — one-click credential copy before launching the client.

<!-- TODO screenshot: settings_view.py — Security/Appearance/Riot API/Launcher/Data tabs -->
![Settings](screenshots/settings.png "Settings — capture app/ui/views/settings_view.py, ideally the Security tab showing auto-lock timeout options")
**Settings** — security, appearance, Riot API key, launcher path, data.

<!-- TODO screenshot: lock_overlay.py — inactivity lock screen -->
![Lock overlay](screenshots/lock_overlay.png "Lock overlay — capture app/ui/components/lock_overlay.py triggered by the inactivity timer, re-authentication prompt visible")
**Lock overlay** — shown automatically after the inactivity timeout.

---

## Features

### Account Management
- Create, edit, and delete accounts with alias, username, password, region, tags, notes, and Riot ID
- 11 regions supported: EUW, EUNE, NA, LAS, LAN, BR, OCE, KR, JP, TR, RU
- Full-text search across alias, username, notes, and tags with advanced operators (`tag:`, `region:`, `"exact phrase"`, `-exclusion`)
- Filter by region and tags with AND logic
- Sort by alias (A-Z / Z-A) or date (newest / oldest)
- Tag autocomplete when creating and editing accounts

### Secure Clipboard
- Copy username, password, or both with one click
- 30-second TTL with a live countdown on the button
- Automatic clipboard wipe on expiry
- Blocking warning when closing with a password on the clipboard

### Password Generator
- Configurable length from 8 to 64 characters (slider)
- Options: uppercase, numbers, symbols, avoid ambiguous characters
- Strength bar with rating and entropy in bits
- "Use password" button that inserts directly into the form

### Password History
- Automatic log of every password change with timestamp
- History modal with masked passwords and show/hide toggle
- Historical passwords are encrypted with the same master key

### Built-in Launcher
- Auto-detects `RiotClientServices.exe` or `LeagueClient.exe`
- Searches common paths (`C:/`, `D:/`, `E:/`), environment variables, and the Windows registry
- Custom path in Settings → Launcher with a file browser button
- Quick-launch dialog with one-click credential copy

### Riot API Integration
- Displays summoner level, rank, and account status on each card
- Local cache per account to minimize API calls
- API key configuration in Settings with show/hide toggle
- Per-card manual refresh button

### Export / Import
- **JSON v1** — encrypted with the current master password (same device)
- **JSON v2** — encrypted with a custom password (portable across installations)
- **CSV** — plaintext with an explicit warning (for migrating to other managers)
- Import with automatic format detection, pre-import summary, and duplicate validation

### Security

| Mechanism | Detail |
|---|---|
| KDF | PBKDF2-HMAC-SHA256, 480,000 iterations (OWASP 2024) |
| Credential encryption | Fernet — AES-128-CBC + HMAC-SHA256 |
| Master password verification | Encrypted Fernet canary (no exposed hash on disk) |
| Storage integrity | SQLite with per-field Fernet encryption; HMAC embedded in JSON exports |
| Passwords in memory | Never in plaintext — decrypted on-demand when copying or viewing history |
| Inactivity lock | Configurable auto-lock (5 / 10 / 15 / 30 / 60 min) with re-authentication overlay |
| Screen capture protection | `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` — window appears black in OBS and recording software while a password is on the clipboard |
| Rate limiting | Increasing delays (2s → 5s → 15s) after failed unlock attempts |
| Atomic writes | `.tmp` + `os.replace()` — no corruption on disk failures |
| Master password change | Re-encrypts all credentials without exposing plaintext on disk |

### Modelo de amenaza

Ningún mecanismo de la tabla anterior implica que el sistema sea "seguro" en abstracto: cada uno mitiga una amenaza concreta, bajo condiciones concretas. Esta sección delimita ese alcance explícitamente.

**Protege contra:**
- Lectura del campo `password` de `vault.db` sin la master password: cada contraseña se cifra individualmente con Fernet (AES-128-CBC + HMAC-SHA256) antes de guardarse en SQLite. *Matiz:* el cifrado es solo de ese campo, no de la fila completa — alias, username, notas, tags y Riot ID se almacenan sin cifrar en la misma base de datos (ver más abajo).
- Captura de pantalla o grabación (OBS y similares) mientras hay username o password copiados en el portapapeles: `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` hace que la ventana aparezca en negro en la grabación mientras el portapapeles está "armado", y se desactiva automáticamente al expirar el TTL de 30s o al bloquearse la sesión por inactividad. Requiere Windows 10 build 2004+; en versiones anteriores no hay protección (la app sigue funcionando, sin este mitigante).
- Fuerza bruta sobre la master password a través de la propia UI: PBKDF2-HMAC-SHA256 con 480.000 iteraciones eleva el coste por intento, y una penalización progresiva corta el ritmo de reintentos (intentos 1-2 sin espera, intento 3 → 2s, intento 4 → 5s, intento 5 en adelante → 15s fijos por intento).
- Corrupción de datos por una escritura interrumpida a mitad de operación: `vault.db` se apoya en las transacciones atómicas propias de SQLite (commit/rollback vía journal); `accounts.json` (formato legado), `settings.json` y las exportaciones JSON usan el patrón fichero `.tmp` + `os.replace()`.

**No protege contra:**
- Un keylogger u otro malware activo en el sistema mientras se teclea la master password: no existe ningún mecanismo anti-keylogging ni de entrada segura.
- Un atacante con acceso físico y privilegios de administrador mientras la vault está desbloqueada: la clave Fernet derivada y la clave de firma HMAC residen en memoria del proceso mientras la sesión está activa, y son recuperables mediante un volcado de memoria o un depurador adjunto al proceso.
- Pérdida de la master password: no hay recuperación posible por diseño. `master.key` solo guarda el salt y un canary cifrado con Fernet (nunca la contraseña ni un hash reversible de ella), así que sin la contraseña original los datos cifrados quedan irrecuperables.
- Lectura de los campos no cifrados de `vault.db` por cualquiera con acceso al fichero: alias, username, notas, tags y Riot ID viajan en texto plano dentro de la base de datos; solo `password` está cifrado. El HMAC de integridad detecta si esos campos fueron modificados externamente, pero no impide que sean leídos.

---

## Getting Started

### Requirements

- Python 3.11+
- Windows 10 (build 19041+) or Windows 11

> Screen capture protection (`SetWindowDisplayAffinity`) requires Windows 10 version 2004 or later. On older versions the app runs normally without that protection.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/nleceguic/rift-vault.git
cd rift-vault

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

---

## Data Storage

All data is saved in `~/.rift_vault/` (user folder):

| File | Contents |
|---|---|
| `master.key` | Salt + encrypted Fernet canary to verify the master password |
| `vault.db` | SQLite database with accounts, password history, and Riot API cache |
| `settings.json` | UI preferences (theme, timeout, Riot API key, launcher path) |

The master password is **never** stored — only the salt and verification token. Every sensitive field in the database is individually Fernet-encrypted. If a legacy `accounts.json` is detected, migration to SQLite happens automatically on first launch.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| UI | CustomTkinter 5.2.2 |
| Encryption | cryptography 48.0.0 (Fernet / PBKDF2) |
| Database | SQLite 3 (stdlib) |
| Images | Pillow 12.2.0 |
| Theme detection | darkdetect 0.8.0 |
| Windows API | ctypes (stdlib) |
| Riot API | requests |

---

## Architecture

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

**Patterns:** Layered Architecture, Repository, Dependency Injection (ServiceRegistry), Pub/Sub (EventBus), Hook System.

---

## Project Structure

```
rift-vault/
├── main.py                              # Entry point
├── requirements.txt
└── app/
    ├── config.py                        # Global constants, color palette, fonts
    ├── core/
    │   ├── account.py                   # Domain model (Account dataclass)
    │   ├── account_service.py           # Business logic, validation, CRUD
    │   ├── crypto_service.py            # PBKDF2 + Fernet + HMAC export signing
    │   ├── event_bus.py                 # Pub/sub for cross-layer communication
    │   ├── service_registry.py          # Dependency injection container
    │   ├── settings_service.py          # User preference persistence
    │   ├── password_generator.py        # Secure generation + strength evaluation
    │   ├── password_history_service.py  # Per-account password history
    │   ├── export_service.py            # Export/import JSON v1, JSON v2, CSV
    │   ├── advanced_search.py           # Search engine with operators
    │   ├── riot_api_service.py          # Riot Games API integration
    │   ├── launcher_service.py          # LoL client detection and launch
    │   ├── error_handler.py             # Global error handling
    │   └── win32_utils.py               # Windows API (capture protection)
    ├── storage/
    │   ├── base_storage.py              # Abstract repository interface
    │   ├── sqlite_storage.py            # SQLite persistence with per-field encryption
    │   └── json_storage.py              # Legacy JSON storage (auto-migration)
    ├── hooks/
    │   ├── base_hook.py                 # Extension interface
    │   └── hooks_registry.py            # Hook registry (active extensibility)
    └── ui/
        ├── app_window.py                # Root window, inactivity timer, navigation
        ├── views/
        │   ├── unlock_view.py           # Login / initial setup
        │   ├── home_view.py             # Dashboard with stats
        │   ├── accounts_view.py         # Account list and management
        │   └── settings_view.py         # Settings (Security, Appearance, Riot API, Launcher, Data)
        └── components/
            ├── account_card.py          # Individual card with copy, edit, history, launch
            ├── account_form_dialog.py   # Create/edit modal with scroll
            ├── filter_bar.py            # Advanced search, filters, sorting
            ├── lock_overlay.py          # Inactivity lock screen
            ├── change_password_dialog.py
            ├── password_generator_dialog.py
            ├── password_history_dialog.py
            ├── launch_dialog.py
            ├── tag_autocomplete.py
            └── tooltip.py
```

---

## Tests

```bash
pytest
```

423 tests covering domain services, storage, encryption, advanced search, password generator, export/import, Riot API, and the launcher.

---

## License

MIT © [nleceguic](https://github.com/nleceguic)
