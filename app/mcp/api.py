from fastmcp import FastMCP
from fastapi import APIRouter

from app.database.db import search_poi

mcp = FastMCP("AI Tools")

mcp_app = mcp.http_app()

router = APIRouter(lifespan=mcp_app.lifespan)

router.mount("/mcp", mcp_app)

@mcp.tool
def ping() -> str:
    return "pong!"

@mcp.tool
def search_poi(
        query: str,
        top_n: int = 5,
        fields: list[str] = None,
        filter_expression: str = ""
) -> list[tuple]:
    """Searches for information within in the vector database. Performs a vector search on a query.
    :param query: String to search for within the database
    :param top_n: Optional, Specifies how many of the top results to return
    :param fields: Optional, Specifies which fields of the result to output
    :param filter_expression: Optional, specifies a filter to use within the scalar results. Format specified here:
    https://milvus.io/docs/boolean.md
    :return: List of tuples of the result and the distance from the query
    """
    return search_poi(query, top_n, fields, filter_expression)