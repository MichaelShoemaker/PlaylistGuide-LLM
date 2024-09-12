import pickle
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# Load the model
model_name = 'multi-qa-MiniLM-L6-cos-v1'
model = SentenceTransformer(model_name)

# Connect to Elasticsearch
es_client = Elasticsearch('http://elasticsearch:9200') 

index_settings = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "text": {"type": "text"},
            "timecode_text": {"type": "text"},
            "description": {"type": "keyword"},
            "id": {"type": "keyword"},
            "title_vector": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            },
            "timecode_vector": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            },
            "text_vector": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            },
            "description_vector": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            },
        }
        }
    }


index_name = "video-content"

es_client.indices.delete(index=index_name, ignore_unavailable=True)
es_client.indices.create(index=index_name, body=index_settings)


# Load the transcripts data
with open('./data/fixed_ground_truth.pkl','rb') as infile:
    data = pickle.load(infile)


# Maked encodings
load_data = []
for i in data:
    d = {}
    d['title'] = i['title']
    d['text'] = i['text']
    d['timecode_text'] = i['timecode_text']
    d['description'] = i['description']
    d['id'] = i['id']
    d['title_vector'] = model.encode(i['title'])
    d['timecode_vector'] = model.encode(i['timecode_text'])
    d['text_vector'] = model.encode(i['text'])
    d['description_vector'] = model.encode(i['description'])
    load_data.append(d)


# Insert documents into Elasticsearch
for doc in load_data:
    try:
        es_client.index(index=index_name, document=doc)
    except Exception as e:
        print(e)