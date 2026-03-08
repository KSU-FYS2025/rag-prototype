import os
from typing import Annotated

from fastapi import Depends, HTTPException
from pymilvus import MilvusClient

import requests
import ollama

from app.database.db import get_db_gen

NeedsDb = Annotated[MilvusClient, Depends(get_db_gen)]
"""
Declares database dependency as an easy to use type.
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-session-dependency
test for github ignore
"""

def needs_ollama():
    error = HTTPException(status_code=404, detail="""Ollama is not running!
            ensure ollama is running on the server before querying this route!""")
    try:
        res = requests.get("http://localhost:11434")
        if res.text != "Ollama is running":
            raise error

        model = os.environ.get("AI_MODEL")
        if model not in [model.model for model in ollama.list()["models"]]:
            raise HTTPException(status_code=404, detail="The specified model in the .env file is not installed"
            "on the ollama server!")
    except:
        raise error

NeedsOllama = Depends(needs_ollama)
