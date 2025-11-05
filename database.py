from pymilvus import MilvusClient
from pymilvus import model

client = MilvusClient("vectorDB.db")
embedding_fn = model.DefaultEmbeddingFunction()

def instantiate_db(settings):
    if client.has_collection(settings["collection_name"]):
        client.drop_collection(settings["collection_name"])
    client.create_collection(**settings)

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

def fill_create_db(settings, file_path):
    instantiate_db(settings)
    data = embed_file(file_path)
    res = client.insert(collection_name=settings["collection_name"], data=data)
    return res
