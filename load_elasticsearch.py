import pickle
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

es = Elasticsearch("http://localhost:9200")
index_name = "video-content"

index_settings = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "timecode": {"type": "text"},
            "text": {"type": "text"},
            "description": {"type": "keyword"} ,
            "link": {"type": "keyword"} ,
            "text_vector": {"type": "keyword"} ,
            "search_vector": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
        }
    }
}

es.indices.delete(index=index_name, ignore_unavailable=True)
es.indices.create(index=index_name, body=index_settings)



with open('transcripts_metadata_records.pkl', 'rb') as infile:
    transcripts = pickle.load(infile)

for transcript in transcripts:
    transcript['text_vector'] = transcript['title']+' '+transcript['text']+' '+transcript['description']
    transcript['search_vector'] = model.encode(transcript['text_vector'])

for doc in transcripts:
    try:
        es.index(index=index_name, document=doc)
    except Exception as e:
        print(e)