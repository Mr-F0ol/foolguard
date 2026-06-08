"""Dependência de autenticação.

`get_current_user` é injetada em qualquer rota que exija login. Ela:
1. Extrai o token JWT do cabeçalho Authorization.
2. Valida o token.
3. Busca o usuário correspondente no banco.

Se qualquer passo falhar, retorna 401 — protegendo as rotas privadas.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise _credentials_error

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise _credentials_error
    return user
