"""Rich console used for everything rendered outside the input area."""

import time

from rich.console import Console

console = Console()


def farewell() -> None:
    """Print a short, dim goodbye after the interface has closed."""
    console.print()
    with console.status("[dim]Shutting down…[/dim]", spinner="dots"):
        time.sleep(0.5)
    console.print("[dim]Paijo is signing off. See you next time 👋[/dim]")
