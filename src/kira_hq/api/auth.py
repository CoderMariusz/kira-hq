"""HTTPBasic auth gate for Module 2 — PRD §4 Module 2 auth, §6.12.

Default: localhost-only → no auth. Enable by setting
`KIRA_HQ_EXPOSED=true` in the environment before starting uvicorn.
Credentials are loaded via `kira_hq.secrets_schema.load_secrets()`
from `~/.kira-hq/.env` (chmod 600): `KIRA_HQ_USER`, `KIRA_HQ_PASS`.

The gate is a FastAPI dependency. Inject it at router level (not
globally) so `/health` stays open — useful for k8s/uvicorn workers
liveness probes without burning credentials on noise.

Security notes:
  - `hmac.compare_digest` for constant-time comparison on BOTH user
    and pass (prevents username enumeration via timing).
  - If flag enabled but creds missing/blank → every request 503. This
    fails LOUD rather than silently allowing through: a misconfigured
    prod deployment must not silently become open.
  - No session cookies, no tokens — just Basic. PRD §6.12 explicitly
    chose "simplest auth that works"; re-evaluate when Next.js needs
    more than one user.
"""
from __future__ import annotations

import hmac
import os
from typing import Callable, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_EXPOSED_ENV_VAR = "KIRA_HQ_EXPOSED"
_USER_KEY = "KIRA_HQ_USER"
_PASS_KEY = "KIRA_HQ_PASS"


def is_exposed() -> bool:
    """True if auth must be enforced. Reads env each call (not cached) so
    tests can flip the flag with monkeypatch without restarting the app."""
    return os.environ.get(_EXPOSED_ENV_VAR, "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _default_secrets_loader() -> Dict[str, str]:
    """Production path — reads ~/.kira-hq/.env via load_secrets()."""
    from kira_hq.secrets_schema import load_secrets  # late import
    # check_perms=False here: the chmod-600 warning fires at server
    # startup via a separate code path; on each request we just need
    # the values. Don't spam stderr on every HTTP call.
    return load_secrets(check_perms=False)


_security = HTTPBasic(auto_error=False)  # we handle 401 shape ourselves


def make_auth_dependency(
    secrets_loader: Optional[Callable[[], Dict[str, str]]] = None,
    *,
    exposed_probe: Optional[Callable[[], bool]] = None,
) -> Callable:
    """Build the FastAPI dependency. Injectable loader/probe for tests.

    Returns a function that, when used via `Depends(...)`, will:
      - no-op if KIRA_HQ_EXPOSED is off (localhost mode)
      - enforce HTTPBasic against loaded secrets otherwise
      - raise 503 if flag on but creds missing (fail-loud)
      - raise 401 on bad creds (with WWW-Authenticate: Basic)
    """
    loader = secrets_loader or _default_secrets_loader
    probe = exposed_probe or is_exposed

    def require_auth(
        credentials: Optional[HTTPBasicCredentials] = Depends(_security),
    ) -> Optional[str]:
        if not probe():
            # Localhost-only mode: skip auth entirely.
            return None

        secrets = loader()
        expected_user = secrets.get(_USER_KEY, "")
        expected_pass = secrets.get(_PASS_KEY, "")
        if not expected_user or not expected_pass:
            # Fail LOUD — refuse to serve until config is fixed.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"{_EXPOSED_ENV_VAR}=true but "
                    f"{_USER_KEY}/{_PASS_KEY} missing in ~/.kira-hq/.env"
                ),
            )

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Basic"},
            )

        # Constant-time compare on BOTH fields (prevents username enum).
        user_ok = hmac.compare_digest(
            credentials.username.encode("utf-8"),
            expected_user.encode("utf-8"),
        )
        pass_ok = hmac.compare_digest(
            credentials.password.encode("utf-8"),
            expected_pass.encode("utf-8"),
        )
        if not (user_ok and pass_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

        return credentials.username

    return require_auth


__all__ = [
    "is_exposed",
    "make_auth_dependency",
]
