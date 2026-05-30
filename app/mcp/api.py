from fastmcp import FastMCP
from fastapi import APIRouter

mcp = FastMCP("AI Tools")

mcp_app = mcp.http_app()

router = APIRouter(lifespan=mcp_app.lifespan)

router.mount("/mcp", mcp_app)

@mcp.tool()
def ping() -> str:
    return "pong!"
