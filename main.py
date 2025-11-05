# Example from https://huggingface.co/blog/ngxson/make-your-own-rag

import ollama
from database import client, embedding_fn, fill_create_db

LANGUAGE_MODEL = 'hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF'

fill_create_db(
    {
        "collection_name": "cat_facts",
        "dimension": 768
    }, "cat-facts.txt"
)

def retrieve(query, top_n = 3):
    query_vectors = embedding_fn.encode_queries([query])
    res = client.search(
        collection_name="cat_facts",
        data=query_vectors,
        limit=top_n,
        output_fields=["texts", "subject"]
    )
    return [(x[0]["entity"], x[0]["distance"]) for x in res]

input_query = input("Ask me a question: ")
retrieved_knowledge = retrieve(input_query)
print("Retrieved knowledge: ")
for chunk, similarity in retrieved_knowledge:
    print(f" - (similiarity: {similarity:.2f}) {chunk}")

instruction_prompt = f"""You are a helpful chatbot.
Use only the following pieces of context to answer the question. Don't make up any new information:
{"\n".join([f" - {chunk}" for chunk, similarity in retrieved_knowledge])}
"""

stream = ollama.chat(
    model=LANGUAGE_MODEL,
    messages=[
        {"role": "system", "content": instruction_prompt},
        {"role": "user", "content": input_query},
    ],
    stream=True
)

print("Chatbot response")
for chunk in stream:
    print(chunk["message"]["content"], end="", flush=True)
