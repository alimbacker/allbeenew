"""Email validation tuned for a self-hosted product.

`email-validator` refuses "special-use" domains by default -- `.local`,
`.test`, `.internal`, `.localhost` and friends. That default suits a public
SaaS, but ALLBEE is designed to run on a photographer's own machine or a
studio LAN, where `admin@studio.local` is a perfectly real address. The
documented demo account, `demo@allbee.local`, is rejected outright otherwise.

So we allow the private-network names and keep every other check: syntax,
length, and normalisation. Deliverability (a DNS/MX lookup) stays off, because
registration must work on a machine with no internet connection.
"""

from __future__ import annotations

import email_validator
from pydantic import EmailStr

# Domains a self-hosted install may legitimately use.
_PRIVATE_NETWORK_DOMAINS = {"local", "localhost", "test", "internal", "home", "lan", "intranet"}

email_validator.SPECIAL_USE_DOMAIN_NAMES = [
    name
    for name in email_validator.SPECIAL_USE_DOMAIN_NAMES
    if name not in _PRIVATE_NETWORK_DOMAINS
]

__all__ = ["EmailStr"]
