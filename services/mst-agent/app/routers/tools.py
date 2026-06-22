from fastapi import APIRouter

from app.nodes_catalog import NODES_CATALOG

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", summary="List all available n8n nodes as tools")
async def list_tools(category: str | None = None, search: str | None = None):
    tools = list(NODES_CATALOG)

    if category:
        tools = [t for t in tools if category.lower() in [c.lower() for c in t["category"]]]

    if search:
        q = search.lower()
        tools = [
            t for t in tools
            if q in t["display_name"].lower() or q in t["description"].lower()
        ]

    return {"count": len(tools), "tools": tools}
