from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
es = Elasticsearch("http://localhost:9200")



def elas_search(index_name, question):
    vector_search_term = model.encode(question)

    query = {
        "field": "search_vector",
        "query_vector": vector_search_term,
        "k": 10,
        "num_candidates": 10000, 
    }

    res = es.search(index=index_name, knn=query, source=["title","link"])
    return res["hits"]["hits"]

if __name__ == "__main__":
    index_name = "video-content"
    question = "Mage Orchestrator?"
    for rec in elas_search(index_name, question):
        print(rec)
