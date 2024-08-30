import os
import pickle
from sentence_transformers import SentenceTransformer
from elasticsearch import Elasticsearch
import streamlit as st
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
import pandas as pd
import openai  # Make sure to install the openai package

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Elasticsearch client
es = Elasticsearch([ELASTICSEARCH_URL])

# Initialize Sentence Transformer
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Connect to PostgreSQL
engine = create_engine(DATABASE_URL)
connection = engine.connect()

# Define index name
index_name = "your_index_name"

# Read pickle file
with open('data/transcripts_metadata_records.pkl', 'rb') as infile:
    transcripts = pickle.load(infile)

# Encode and transform data
for transcript in transcripts:
    transcript['text_vector'] = transcript['title'] + ' ' + transcript['text'] + ' ' + transcript['description']
    transcript['search_vector'] = model.encode(transcript['text_vector'])

# Index documents in Elasticsearch
es.indices.delete(index=index_name, ignore_unavailable=True)
es.indices.create(index=index_name, body={
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "timecode": {"type": "text"},
            "text": {"type": "text"},
            "description": {"type": "keyword"},
            "link": {"type": "keyword"},
            "text_vector": {"type": "keyword"},
            "search_vector": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
        }
    }
})

for i, doc in enumerate(transcripts):
    es.index(index=index_name, id=i, body=doc)

# Set up OpenAI API key
openai.api_key = OPENAI_API_KEY

# Streamlit app
st.title("Search and Feedback")

# Search form
query = st.text_input("Enter your question:")
if query:
    query_vector = model.encode(query)
    
    search_query = {
        "field": "search_vector",
        "query_vector": query_vector,
        "k": 10,
        "num_candidates": 10000,
    }
    
    response = es.search(index=index_name, knn=search_query, source=["title", "link", "text", "timecode"])
    hits = response["hits"]["hits"]
    
    # Create context from search results
    context = " ".join([hit["_source"]["text"] for hit in hits])
    
    # Call OpenAI's LLM
    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
    
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",  # or any other available model
            prompt=prompt,
            max_tokens=150
        )
        answer = response.choices[0].text.strip()
    except Exception as e:
        answer = f"Error querying OpenAI API: {str(e)}"
    
    # Display results
    st.write("Results:")
    for hit in hits:
        source = hit["_source"]
        st.write(f"**Title:** {source['title']}")
        st.write(f"**Link:** [Watch here]({source['link']})")
        st.write(f"**Text:** {source['text']}")
        st.write(f"**Timecode:** {source['timecode']}")
        st.write("---")
    
    st.write("**Answer from LLM:**")
    st.write(answer)
    
    # Feedback form
    feedback = st.radio("Was this answer helpful?", ["Yes", "No"])
    if st.button("Submit Feedback"):
        user_id = st.text_input("Enter your user ID:")
        session_id = st.text_input("Enter your session ID:")
        
        feedback_data = {
            "question": query,
            "feedback": feedback,
            "user_id": user_id,
            "session_id": session_id
        }
        
        # Save feedback to PostgreSQL
        df = pd.DataFrame([feedback_data])
        df.to_sql('feedback', con=engine, if_exists='append', index=False)
        st.success("Feedback submitted!")
