from pymilvus import MilvusClient
from tqdm import tqdm
from glob import glob

text_lines = {}

for file_path in glob("milvus_docs/en/faq/*.md", recursive = True):
    with open(file_path, "r", encoding="utf-8") as file:
        '''file_text = file.read()'''

    #text_lines +=file_text.split("# ")

data = []

for i, line in enumerate(tqdm(text_lines, desc = "Creating embeddings")):
    data.append({"id": i, "vector": '''emb_text(line)''', "text":line})

import ollama

milvus_client = MilvusClient()

collection_name = "descriptions"

def emb_text(text):
    return(

)

if milvus_client.has_collection(collection_name):
    milvus_client.drop_collection(collection_name)

milvus_client.create_collection(
    collection_name=collection_name,
    #dimension=embedding_dim,
    metric_type="IP",
    consistency_level = "Bounded"
)

input = input("Please enter object description: ")

serch_res = milvus_client.search(
    collection_name = collection_name,
    data = [
        emb_text(input)
    ],
    limit = 3,
    search_params = {"metrtic_type": "IP", "params": {}},
    output_fields = ["text"],
)

