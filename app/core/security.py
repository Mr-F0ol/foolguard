"""Funções de segurança: hashing de senhas e tokens JWT.

Este módulo concentra toda a lógica sensível de segurança em um só lugar,
o que facilita auditoria — uma prática que você vai querer destacar no seu
threat model mais adiante.

Decisões de segurança aplicadas aqui:
- Senhas NUNCA são armazenadas em texto puro. Usamos bcrypt, que é lento
  de propósito (resistente a ataques de força bruta).
- Tokens JWT são assinados com a SECRET_KEY e expiram, limitando a janela
  de uso caso um token vaze.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    """Gera o hash seguro de uma senha em texto puro usando bcrypt."""
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se uma senha corresponde ao hash armazenado."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(subject: str) -> str:
    """Cria um token JWT assinado para o usuário identificado por `subject`.

    `subject` normalmente é o ID do usuário. O token carrega a data de
    expiração (`exp`), que o cliente deve respeitar.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    """Decodifica e valida um token JWT.

    Retorna o `subject` (ID do usuário) se o token for válido, ou None se
    for inválido/expirado. A biblioteca já verifica a assinatura e a
    expiração automaticamente.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None
