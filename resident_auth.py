import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Optional, Tuple

from flask import current_app

from db import get_conn
import user_model


class ResidentTokenError(ValueError):
    pass


class ResidentTokenExpiredError(ResidentTokenError):
    pass


def _now_timestamp() -> int:
    return int(time.time())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('ascii'))


def _json_bytes(payload: Dict) -> bytes:
    return json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')


def _get_secret() -> bytes:
    secret = (
        current_app.config.get('RESIDENT_API_JWT_SECRET')
        or current_app.config.get('SECRET_KEY')
        or ''
    )
    if not secret:
        raise RuntimeError('SECRET_KEY no configurada para tokens JWT')
    return str(secret).encode('utf-8')


def _sign(signing_input: bytes) -> str:
    signature = hmac.new(_get_secret(), signing_input, hashlib.sha256).digest()
    return _b64url_encode(signature)


def _build_token_payload(user, token_type: str, expires_in_seconds: int) -> Dict:
    issued_at = _now_timestamp()
    return {
        'sub': str(user.id),
        'role': user.role,
        'type': token_type,
        'iss': current_app.config.get('RESIDENT_API_JWT_ISSUER', 'toscana-resident-api'),
        'iat': issued_at,
        'nbf': issued_at,
        'exp': issued_at + expires_in_seconds,
        'jti': secrets.token_hex(8),
    }


def _encode_token(payload: Dict) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    encoded_header = _b64url_encode(_json_bytes(header))
    encoded_payload = _b64url_encode(_json_bytes(payload))
    signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
    signature = _sign(signing_input)
    return f'{encoded_header}.{encoded_payload}.{signature}'


def _build_token(user, token_type: str, expires_in_seconds: int) -> Tuple[str, Dict]:
    payload = _build_token_payload(user, token_type, expires_in_seconds)
    return _encode_token(payload), payload


def _store_refresh_token(user_id: int, refresh_payload: Dict) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO resident_api_refresh_tokens (user_id, jti, expires_at, issued_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, refresh_payload['jti'], int(refresh_payload['exp']), int(refresh_payload['iat'])),
        )
        conn.commit()
    finally:
        conn.close()


def _get_refresh_token_row(jti: str, user_id: Optional[int] = None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                "SELECT user_id, jti, expires_at, issued_at, revoked_at, replaced_by_jti FROM resident_api_refresh_tokens WHERE jti = ? LIMIT 1",
                (jti,),
            )
        else:
            cur.execute(
                "SELECT user_id, jti, expires_at, issued_at, revoked_at, replaced_by_jti FROM resident_api_refresh_tokens WHERE jti = ? AND user_id = ? LIMIT 1",
                (jti, user_id),
            )
        return cur.fetchone()
    finally:
        conn.close()


def _ensure_refresh_token_active(user_id: int, jti: str) -> None:
    row = _get_refresh_token_row(jti, user_id=user_id)
    if not row:
        raise ResidentTokenError('Refresh token no reconocido')
    if row['revoked_at'] is not None:
        raise ResidentTokenError('Refresh token revocado')
    if int(row['expires_at']) <= _now_timestamp():
        raise ResidentTokenExpiredError('Refresh token expirado')


def issue_token_pair(user, rotate_from_refresh_jti: Optional[str] = None) -> Dict:
    if user.role != 'resident':
        raise ResidentTokenError('Solo los residentes pueden recibir tokens móviles')

    access_lifetime_seconds = int(current_app.config.get('RESIDENT_API_ACCESS_TOKEN_MINUTES', 15)) * 60
    refresh_lifetime_seconds = int(current_app.config.get('RESIDENT_API_REFRESH_TOKEN_DAYS', 30)) * 24 * 60 * 60
    access_token, access_payload = _build_token(user, 'access', access_lifetime_seconds)
    refresh_token, refresh_payload = _build_token(user, 'refresh', refresh_lifetime_seconds)
    _store_refresh_token(user.id, refresh_payload)

    if rotate_from_refresh_jti:
        revoke_refresh_token_by_jti(
            rotate_from_refresh_jti,
            user_id=user.id,
            replaced_by_jti=refresh_payload['jti'],
        )

    return {
        'token_type': 'Bearer',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'access_expires_in': access_lifetime_seconds,
        'refresh_expires_in': refresh_lifetime_seconds,
        'access_jti': access_payload['jti'],
        'refresh_jti': refresh_payload['jti'],
    }


def decode_token(token: str, expected_type: str = 'access', validate_exp: bool = True) -> Dict:
    token = (token or '').strip()
    if not token:
        raise ResidentTokenError('Token requerido')

    parts = token.split('.')
    if len(parts) != 3:
        raise ResidentTokenError('Formato de token invalido')

    encoded_header, encoded_payload, encoded_signature = parts

    try:
        header = json.loads(_b64url_decode(encoded_header))
        payload = json.loads(_b64url_decode(encoded_payload))
    except Exception as exc:
        raise ResidentTokenError('No se pudo decodificar el token') from exc

    if header.get('alg') != 'HS256' or header.get('typ') != 'JWT':
        raise ResidentTokenError('Algoritmo de token no soportado')

    signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise ResidentTokenError('Firma de token invalida')

    now = _now_timestamp()
    if int(payload.get('nbf', 0)) > now:
        raise ResidentTokenError('Token aun no valido')
    if validate_exp and int(payload.get('exp', 0)) <= now:
        raise ResidentTokenExpiredError('Token expirado')
    if payload.get('iss') != current_app.config.get('RESIDENT_API_JWT_ISSUER', 'toscana-resident-api'):
        raise ResidentTokenError('Issuer de token invalido')
    if payload.get('type') != expected_type:
        raise ResidentTokenError('Tipo de token invalido')

    return payload


def get_user_from_token(token: str, expected_type: str = 'access', required_role: str = 'resident',
                        require_active_refresh: bool = False, validate_exp: bool = True) -> Tuple[object, Dict]:
    payload = decode_token(token, expected_type=expected_type, validate_exp=validate_exp)

    try:
        user_id = int(payload.get('sub'))
    except Exception as exc:
        raise ResidentTokenError('Subject de token invalido') from exc

    user = user_model.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise ResidentTokenError('Usuario asociado al token no disponible')
    if required_role and user.role != required_role:
        raise ResidentTokenError('Rol del token no autorizado')
    if expected_type == 'refresh' and require_active_refresh:
        _ensure_refresh_token_active(user.id, payload['jti'])

    return user, payload


def revoke_refresh_token(refresh_token: str, user_id: Optional[int] = None,
                         replaced_by_jti: Optional[str] = None) -> int:
    user, payload = get_user_from_token(
        refresh_token,
        expected_type='refresh',
        required_role='resident',
        require_active_refresh=False,
        validate_exp=False,
    )
    if user_id is not None and user.id != user_id:
        raise ResidentTokenError('Refresh token no pertenece al usuario autenticado')
    return revoke_refresh_token_by_jti(payload['jti'], user_id=user.id, replaced_by_jti=replaced_by_jti)


def revoke_refresh_token_by_jti(jti: str, user_id: Optional[int] = None,
                                replaced_by_jti: Optional[str] = None) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                """
                UPDATE resident_api_refresh_tokens
                SET revoked_at = ?,
                    replaced_by_jti = COALESCE(?, replaced_by_jti)
                WHERE jti = ? AND revoked_at IS NULL
                """,
                (_now_timestamp(), replaced_by_jti, jti),
            )
        else:
            cur.execute(
                """
                UPDATE resident_api_refresh_tokens
                SET revoked_at = ?,
                    replaced_by_jti = COALESCE(?, replaced_by_jti)
                WHERE jti = ? AND user_id = ? AND revoked_at IS NULL
                """,
                (_now_timestamp(), replaced_by_jti, jti, user_id),
            )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def revoke_all_refresh_tokens_for_user(user_id: int) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE resident_api_refresh_tokens
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (_now_timestamp(), user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()