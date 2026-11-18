"""Encryption for stored social media tokens."""
from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:"

GENERATE_HINT = (
    'generate one with: python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())"'
)


class SecretBox:
    def __init__(self, key: str):
        if not key:
            raise ValueError(f"ENCRYPTION_KEY is required; {GENERATE_HINT}")
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError):
            raise ValueError(f"ENCRYPTION_KEY is not a valid key; {GENERATE_HINT}") from None

    @staticmethod
    def is_encrypted(value) -> bool:
        return isinstance(value, str) and value.startswith(PREFIX)

    def encrypt(self, value: str) -> str:
        return PREFIX + self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value):
        """Decrypt a stored value. Values saved before encryption existed are returned as-is."""
        if value is None or not self.is_encrypted(value):
            return value
        try:
            return self._fernet.decrypt(value[len(PREFIX):].encode()).decode()
        except InvalidToken:
            raise ValueError("Stored token can't be decrypted: was ENCRYPTION_KEY changed?") from None
