"""MCP surface of Sahayak: three tools + one resource, thin wrappers over the service."""

import json
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from sahayak.retrieve.types import Passage
from sahayak.service import BudgetExceededError, SahayakService, Verdict

INSTRUCTIONS = (
    "Search and cite Reserve Bank of India (RBI) Master Directions in Hindi and English. "
    "Use search_docs to find passages, get_passage to read one, and verify_claim before "
    "asserting anything. Always cite chunk_ids."
)


def build_mcp(service: SahayakService) -> FastMCP:
    mcp = FastMCP("sarkari-sahayak", instructions=INSTRUCTIONS)

    @mcp.tool
    def search_docs(
        query: Annotated[str, Field(min_length=2, max_length=500, description="Hindi or English")],
        k: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> list[Passage]:
        """Hybrid (BM25 + dense) search over RBI documents. Returns passages, best first."""
        return service.search(query, k)

    @mcp.tool
    def get_passage(chunk_id: Annotated[str, Field(min_length=3, max_length=200)]) -> Passage:
        """Fetch one passage by its chunk_id (e.g. 'MD-KYC-2016#p4c0')."""
        found = service.get_passage(chunk_id)
        if found is None:
            raise ToolError(f"unknown chunk_id: {chunk_id}")
        return found

    @mcp.tool
    def verify_claim(
        claim: Annotated[str, Field(min_length=5, max_length=1000)],
        chunk_ids: Annotated[list[str], Field(min_length=1, max_length=10)],
    ) -> Verdict:
        """Check whether the given passages support the claim."""
        try:
            return service.verify_claim(claim, chunk_ids)
        except BudgetExceededError as exc:
            raise ToolError("daily budget exhausted; try search_docs instead") from exc

    @mcp.resource("sahayak://docs/{doc_id}", mime_type="application/json")
    def document(doc_id: str) -> str:
        """Metadata and first passage of a source document."""
        first = service.get_passage(f"{doc_id}#p1c0")
        if first is None:
            raise ToolError(f"unknown doc_id: {doc_id}")
        return json.dumps(
            {"doc_id": doc_id, "title": first.title, "source_url": first.source_url},
            ensure_ascii=False,
        )

    return mcp
