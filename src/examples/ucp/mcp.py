"""MCP transport for the UTCS core. Speaks TransactionContext, not the UCP wire."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from bindings.ucp.errors import BindingError
from bindings.ucp.models import TransactionContext
from examples.ucp.determine import MockDeterminer


def build_server(determiner: MockDeterminer | None = None) -> FastMCP:
    engine = determiner or MockDeterminer()
    mcp = FastMCP(
        name="utcs",
        instructions=(
            "UTCS tax determination. utcs_determine_tax takes a TransactionContext "
            "and returns a TaxResult. commit false is an estimate. commit true "
            "records compliance state. This process uses the mock provider."
        ),
    )

    @mcp.tool(name="utcs_determine_tax")
    def utcs_determine_tax(context: dict[str, Any]) -> dict[str, Any]:
        """Calculate tax for a commerce transaction.

        Amounts are UTCS decimal strings. commit true records the result.
        """
        try:
            parsed = TransactionContext.model_validate(context)
            result = engine(parsed)
        except BindingError as exc:
            raise ValueError(exc.content) from exc
        return result.model_dump()

    return mcp


def main() -> None:
    build_server().run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
