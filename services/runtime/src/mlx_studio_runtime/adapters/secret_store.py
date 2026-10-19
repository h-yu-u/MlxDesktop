"""macOS Keychain only. No file, environment, or plaintext fallback."""

import sys
import uuid

from keyring.backends.macOS import Keyring
from keyring.errors import KeyringError

from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


class KeychainSecrets:
    service = "MLX Studio Web Search"

    def put(self, value: str) -> str:
        reference = str(uuid.uuid4())
        self._require_macos()
        try:
            Keyring().set_password(self.service, reference, value)
        except KeyringError as error:
            raise self._unavailable() from error
        return reference

    def resolve(self, reference: str) -> str:
        self._require_macos()
        try:
            value = Keyring().get_password(self.service, reference)
        except KeyringError as error:
            raise self._unavailable() from error
        if not value:
            raise self._unavailable()
        return value

    def delete(self, reference: str) -> None:
        self._require_macos()
        try:
            Keyring().delete_password(self.service, reference)
        except KeyringError as error:
            raise self._unavailable() from error

    @staticmethod
    def _require_macos() -> None:
        if sys.platform != "darwin":
            raise KeychainSecrets._unavailable()

    @staticmethod
    def _unavailable() -> RuntimeFault:
        return RuntimeFault(
            RuntimeErrorInfo("WEB_CREDENTIAL_UNAVAILABLE", "系统安全存储不可用或凭据已撤销")
        )
