import pickle
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# Load the model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Connect to Elasticsearch
es = Elasticsearch("http://elasticsearch:9200")
index_name = "video-content"

# Define the index settings
index_settings = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "vid_id": {"type": "text"},
            "title": {"type": "text"},
            "timecode": {"type": "text"},
            "text": {"type": "text"},
            "timecode_text": {"type": "text"},
            "description": {"type": "keyword"},
            "link": {"type": "keyword"},
            "id": {"type": "keyword"},
            "text_vector": {"type": "keyword"},
            "search_vector": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
        }
    }
}

# Delete existing index if it exists, then create a new one
es.indices.delete(index=index_name, ignore_unavailable=True)
es.indices.create(index=index_name, body=index_settings)

# Load the transcripts data
with open('/app/data/elastic_search_data.pkl', 'rb') as infile:
    transcripts = pickle.load(infile)

# Insert documents into Elasticsearch
for doc in transcripts:
    try:
        es.index(index=index_name, document=doc)
    except Exception as e:
        print(f"Failed to index document {doc}: {e}")
