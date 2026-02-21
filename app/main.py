from fastapi import FastAPI

from app.poi import api as poiapi
from app.AI import api as aiapi
from app.websockets import api as wsapi

app = FastAPI()

app.include_router(poiapi.router)
app.include_router(aiapi.router)
app.include_router(wsapi.router)

@app.get("/ping")
async def pong():
    return {"message": "pong!"}
