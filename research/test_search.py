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
    index_name = "full_transcripts"
    question = "How do we run elasticsearch in docker?"
    for rec in elas_search(index_name, question):
        print(rec['_source'])
