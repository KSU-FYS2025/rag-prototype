import os
from typing import Annotated

from fastapi import Depends, HTTPException
from pymilvus import MilvusClient

import requests
import ollama

from app.database.db import get_db_dep

NeedsDb = Annotated[MilvusClient, Depends(get_db_dep)]
"""
Declares database dependency as an easy to use type.
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-session-dependency
"""


def needs_ollama():
    ollama_host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    error = HTTPException(
        status_code=404,
        detail=f"""Ollama is not running!
            ensure ollama is running on address {ollama_host} before querying this route!""",
    )
    try:
        res = requests.get(f"http://{ollama_host}")
        if res.text != "Ollama is running":
            raise error

        model = os.environ.get("AI_MODEL")
        if model not in [model.model for model in ollama.list()["models"]]:
            raise HTTPException(
                status_code=404,
                detail="The specified model in the .env file is not installed "
                "on the ollama server!",
            )
    except Exception as e:
        raise e


NeedsOllama = Depends(needs_ollama)
