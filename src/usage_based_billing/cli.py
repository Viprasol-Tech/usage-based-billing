"""Command-line interface for Usage-Based Billing.

``usage-based-billing demo`` meters some synthetic usage for a customer and
prints a fully-priced invoice — graduated API calls, volume-priced storage, and
a flat seat charge — entirely offline.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from usage_based_billing import __version__
from usage_based_billing.invoice import build_invoice
from usage_based_billing.meter import Meter
from usage_based_billing.plans import demo_plan

app = typer.Typer(add_completion=False, help="Usage-Based Billing — by Viprasol Tech.")
console = Console()


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"usage-based-billing [bold cyan]{__version__}[/] — by Viprasol Tech")


@app.command()
def demo(customer: str = typer.Option("acme-corp", help="Customer to invoice.")) -> None:
    """Meter synthetic usage and print an invoice, fully offline."""
    start = datetime(2025, 1, 1)
    end = datetime(2025, 2, 1)
    meter = Meter()

    # 1,200 API calls across the month (graduated pricing).
    day = start
    while day < end:
        meter.record(customer, "api_calls", 40, day)
        day += timedelta(days=1)
    # A few storage readings totalling 1,200 GB (volume pricing).
    meter.record(customer, "storage_gb", 500, start + timedelta(days=1))
    meter.record(customer, "storage_gb", 700, start + timedelta(days=15))
    # Flat per-seat charge.
    meter.record(customer, "seats", 5, start)

    plan = demo_plan()
    invoice = build_invoice(meter, plan, customer, start, end)

    table = Table(title=f"Invoice - {invoice.customer} ({plan.name})")
    table.add_column("Metric", style="cyan")
    table.add_column("Quantity", justify="right")
    table.add_column(f"Amount ({invoice.currency})", justify="right", style="green")
    for item in invoice.line_items:
        table.add_row(item.metric, f"{item.quantity:,}", f"{item.amount:,.2f}")
    table.add_section()
    table.add_row("[bold]TOTAL[/]", "", f"[bold]{invoice.total:,.2f}[/]")
    console.print(table)


__all__ = ["app"]


if __name__ == "__main__":
    app()
