from fastapi import FastAPI

from app.test.api import subapp, lifespan

app = FastAPI(lifespan=lifespan)

app.mount("/test", subapp)

@app.get("/ping")
async def pong():
    return {"message": "pong!"}
