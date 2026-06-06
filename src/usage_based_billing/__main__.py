"""Enable ``python -m usage_based_billing`` to invoke the CLI.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from usage_based_billing.cli import app

if __name__ == "__main__":
    app()
