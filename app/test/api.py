from contextlib import asynccontextmanager
from typing import Union
from httpx import ConnectError

import ollama
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from urllib3.exceptions import ResponseError

from app.database.db import client, create_collection
from pymilvus import model

from app.dependencies import NeedsDb, NeedsOllama

"""
This file contains the example code from the hugging face article.
This is just a test. Make sure to remove this in production.
"""

embedding_fn = model.DefaultEmbeddingFunction()

LANGUAGE_MODEL = 'hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF'


def embed_file(file_path):
    docs = []
    with open(file_path, "r") as file:
        docs = file.readlines()
        print("file successfully loaded")

    vectors = embedding_fn.encode_documents(docs)
    data = [
        {"id": i, "vector": vectors[i], "text": docs[i], "subject": "history"}
        for i in range(len(vectors))
    ]

    return data

def retrieve(query, db, top_n = 3):
    query_vectors = embedding_fn.encode_queries([query])
    with db as db:
        res = db.search(
            collection_name="cat_facts",
            data=query_vectors,
            limit=top_n,
            output_fields=["texts", "subject"]
        )
    return [(x[0]["entity"], x[0]["distance"]) for x in res]

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Running lifespan manager")
    if not client.has_collection("cat_facts"):
        create_collection({
            "collection_name": "cat_facts",
            "dimension": 768
        })
        data = embed_file("cat-facts.txt")
        client.insert(collection_name="cat_facts", data=data)
    yield

subapp = FastAPI(lifespan=lifespan)

@subapp.get("/query/", dependencies=[NeedsOllama])
async def get_query(query: str, db: NeedsDb) -> StreamingResponse:
    retrieved_knowledge = retrieve(query, db)

    instruction_prompt = f"""You are a helpful chatbot.
        Use only the following pieces of context to answer the question. Don't make up any new information:
        {"\n".join([f" - {chunk}" for chunk, similarity in retrieved_knowledge])}
        """

    stream = ollama.chat(
        model=LANGUAGE_MODEL,
        messages=[
            {"role": "system", "content": instruction_prompt},
            {"role": "user", "content": query},
        ],
        stream=True
    )

    async def response():
        for chunk in stream:
            yield chunk["message"]["content"]

    return StreamingResponse(response())
