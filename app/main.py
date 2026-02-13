from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.test.api import subapp, lifespan
from app.poi import api as poiapi
from app.AI import api as aiapi

app = FastAPI(lifespan=lifespan)
# change this later to a routers file to make this easier
app.include_router(poiapi.router)
app.include_router(aiapi.router)

# app.mount("/test", subapp)

@app.get("/ping") #this is A Python Decorator. This tells the program to run a get-route to ping (it's in the code, use your eyes)
async def pong():
    return {"message": "pong!"} #This is what is returned when the route is called

#use the command IN TERMINAL IDIOT: uv run fastapi dev