from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.test.api import subapp, lifespan
from app.poi import api

app = FastAPI(lifespan=lifespan)
# change this later to a routers file to make this easier
app.include_router(api.router)

app.mount("/test", subapp)

@app.get("/ping")
async def pong():
    return {"message": "pong!"}
