"""Emit a JWT token signed with the configured JWT_SECRET.

Usage (with the venv active):

    python scripts/issue_token.py
    python scripts/issue_token.py --subject erp-laravel --expires-in 86400
    python scripts/issue_token.py --claim organization_id=550e8400-e29b-41d4-a716-446655440000

The token uses HS256 and respects JWT_SECRET / JWT_ALGORITHM from your .env.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jose import jwt  # noqa: E402

from app.config import get_settings  # noqa: E402


def parse_claim(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"Invalid claim '{raw}', expected key=value")
    key, value = raw.split("=", 1)
    return key.strip(), value.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a dev JWT token")
    parser.add_argument("--subject", default="dev", help="sub claim (default: dev)")
    parser.add_argument(
        "--expires-in",
        type=int,
        default=3600,
        help="Lifetime in seconds (default: 3600)",
    )
    parser.add_argument(
        "--claim",
        action="append",
        type=parse_claim,
        default=[],
        metavar="KEY=VALUE",
        help="Extra claims (repeat to add more)",
    )
    parser.add_argument(
        "--header",
        action="store_true",
        help="Also print the full Authorization header",
    )
    args = parser.parse_args()

    settings = get_settings()
    now = int(time.time())
    claims: dict = {
        "sub": args.subject,
        "iat": now,
        "exp": now + args.expires_in,
    }
    for key, value in args.claim:
        claims[key] = value

    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    if args.header:
        print(f"Authorization: Bearer {token}")
    else:
        print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
