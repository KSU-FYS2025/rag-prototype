import os
import sys

# mock environment
os.environ["SEARCH_MODE"] = "in_memory"
sys.path.append("/Users/yzhao20/Documents/GitHub/rag-prototype")

from app.database.db import search_poi

res = search_poi("Take me to room 1110", top_n=2, fields=["id", "name"])
print("RES:", res)
