"""Gestión de clave maestra y operaciones de cifrado/descifrado con Fernet."""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import DATA_DIR, KEY_FILE

logger = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 480_000
_SALT_BYTES        = 32
_KEY_FILE_VERSION  = 2

# Valor conocido cifrado con la clave derivada; sirve como oráculo de verificación.
# Al ser un token Fernet, incluye HMAC-SHA256 propio: una clave incorrecta
# produce un fallo de autenticación sin revelar información sobre la clave correcta.
_CANARY_PLAINTEXT = b"RIFT_VAULT_CANARY_V2"


class CryptoService:
    """
    Gestiona la clave maestra y las operaciones de cifrado/descifrado.
    _fernet es None cuando la app está bloqueada.
    """

    def __init__(self, key_file: str = KEY_FILE):
        self._key_file    = key_file
        self._fernet:      Optional[Fernet] = None
        self._signing_key: Optional[bytes]  = None  # clave HMAC separada de la Fernet
        os.makedirs(DATA_DIR, exist_ok=True)

    @property
    def is_unlocked(self) -> bool:
        return self._fernet is not None

    @property
    def is_configured(self) -> bool:
        return os.path.exists(self._key_file)

    def lock(self) -> None:
        self._fernet      = None
        self._signing_key = None

    def setup(self, master_password: str) -> None:
        """Genera salt, deriva clave y persiste el canary cifrado en master.key."""
        if not master_password:
            raise ValueError("La contraseña maestra no puede estar vacía.")

        salt           = secrets.token_bytes(_SALT_BYTES)
        key            = self._derive_key(master_password, salt)
        self._fernet   = self._activate_keys(key)
        canary         = self._fernet.encrypt(_CANARY_PLAINTEXT).decode("utf-8")

        data = {
            "version":    _KEY_FILE_VERSION,
            "kdf":        "pbkdf2-hmac-sha256",
            "iterations": _PBKDF2_ITERATIONS,
            "salt":       salt.hex(),
            "canary":     canary,
        }
        with open(self._key_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("Clave maestra configurada y guardada en %s.", self._key_file)

    def unlock(self, master_password: str) -> bool:
        """Intenta desbloquear; migra automáticamente el formato v1 a v2."""
        if not self.is_configured:
            return False

        data = self._load_key_file()

        if "version" not in data:
            # Formato v1 legacy: verificación SHA256
            return self._unlock_v1_and_migrate(master_password, data)

        return self._unlock_v2(master_password, data)

    def change_password(self, old_password: str, new_password: str, storage=None) -> bool:
        """Verifica la contraseña actual y aplica la nueva, re-cifrando el storage."""
        if not self.unlock(old_password):
            return False
        if not new_password:
            return False
        old_fernet     = self._fernet
        old_signing_key = self._signing_key
        self.setup(new_password)
        if storage is not None:
            storage.rekey(old_fernet, old_signing_key, self)
        return True

    def encrypt(self, plaintext: str) -> str:
        """Cifra y devuelve token Fernet como string."""
        if not self._fernet:
            raise RuntimeError("La app está bloqueada.")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """Descifra un token Fernet. Lanza ValueError si es inválido."""
        if not self._fernet:
            raise RuntimeError("La app está bloqueada.")
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise ValueError("Token inválido o datos corruptos.")

    def sign(self, data: bytes) -> str:
        """
        Devuelve HMAC-SHA256 de `data` como hex string.
        Usa una clave derivada con dominio separado de la clave Fernet
        para evitar reutilización de clave entre cifrado y firma.
        """
        if not self._signing_key:
            raise RuntimeError("La app está bloqueada.")
        return hmac.new(self._signing_key, data, hashlib.sha256).hexdigest()

    def verify_signature(self, data: bytes, signature: str) -> bool:
        """Verifica HMAC-SHA256 de forma resistente a timing attacks."""
        try:
            expected = self.sign(data)
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    def _unlock_v2(self, master_password: str, data: dict) -> bool:
        """Verificación v2: intenta descifrar el canary Fernet."""
        salt = bytes.fromhex(data["salt"])
        key  = self._derive_key(master_password, salt)
        try:
            plaintext = Fernet(key).decrypt(data["canary"].encode("utf-8"))
        except InvalidToken:
            return False

        if plaintext != _CANARY_PLAINTEXT:
            return False

        self._fernet = self._activate_keys(key)
        return True

    def _unlock_v1_and_migrate(self, master_password: str, data: dict) -> bool:
        """Verifica con el formato legacy SHA256 y migra a v2 si tiene éxito."""
        salt     = bytes.fromhex(data["salt"])
        key      = self._derive_key(master_password, salt)
        expected = data["verification_hash"]
        actual   = hashlib.sha256(key).hexdigest()

        if not hmac.compare_digest(expected, actual):
            return False

        self._fernet = self._activate_keys(key)

        # Migrar a v2: reescribir con canary Fernet
        canary = self._fernet.encrypt(_CANARY_PLAINTEXT).decode("utf-8")
        new_data = {
            "version":    _KEY_FILE_VERSION,
            "kdf":        "pbkdf2-hmac-sha256",
            "iterations": _PBKDF2_ITERATIONS,
            "salt":       data["salt"],
            "canary":     canary,
        }
        with open(self._key_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2)

        return True

    def _activate_keys(self, key: bytes) -> Fernet:
        """Inicializa _fernet y _signing_key con separación de dominio."""
        fernet = Fernet(key)
        raw    = base64.urlsafe_b64decode(key)
        self._signing_key = hashlib.sha256(b"RIFT_VAULT_FILE_HMAC" + raw).digest()
        return fernet

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """PBKDF2-HMAC-SHA256 → clave Fernet URL-safe base64 de 32 bytes."""
        raw = hashlib.pbkdf2_hmac(
            hash_name=  "sha256",
            password=   password.encode("utf-8"),
            salt=       salt,
            iterations= _PBKDF2_ITERATIONS,
            dklen=      32,
        )
        return base64.urlsafe_b64encode(raw)

    def _load_key_file(self) -> dict:
        with open(self._key_file, "r", encoding="utf-8") as f:
            return json.load(f)
