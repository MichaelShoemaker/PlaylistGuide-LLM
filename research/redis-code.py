import os
import json
from redis import StrictRedis
from dotenv import load_dotenv
import streamlit as st
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import psycopg2
from datetime import datetime

# Load environment variables
load_dotenv()

# Get environment variables
elasticsearch_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
elasticsearch_port = os.getenv("ELASTICSEARCH_PORT", "9200")
elasticsearch_url = f"http://{elasticsearch_host}:{elasticsearch_port}"
openai_api_key = os.getenv("OPENAI_API_KEY", "your_default_openai_key")
postgres_user = os.getenv("POSTGRES_USER", "db_user")
postgres_password = os.getenv("POSTGRES_PASSWORD", "admin")
postgres_db = os.getenv("POSTGRES_DB", "feedback")
postgres_host = os.getenv("POSTGRES_HOST", "db")
postgres_port = os.getenv("POSTGRES_PORT", "5432")
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))

# Initialize connections
es = Elasticsearch(elasticsearch_url)
model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')

# Initialize Redis client
redis_client = StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Cache the embedding and answer in Redis with 24-hour expiration
def cache_answer_with_embedding(question, embedding, answer):
    redis_key = json.dumps(embedding)  # Convert embedding to JSON string
    redis_value = json.dumps({'question': question, 'answer': answer})
    
    # Store embedding and answer with an expiration of 24 hours (86400 seconds)
    redis_client.setex(redis_key, 86400, redis_value)

# Retrieve the closest match from the cache using cosine similarity
def get_similar_cached_answer(question_embedding):
    for key in redis_client.keys():
        cached_embedding = json.loads(key)
        similarity = cosine_similarity(cached_embedding, question_embedding)
        
        if similarity >= SIMILARITY_THRESHOLD:
            cached_data = json.loads(redis_client.get(key))
            return cached_data['answer'], cached_data['question'], similarity
    
    return None, None, None

# Initialize PostgreSQL database with required table
def init_db():
    try:
        conn = psycopg2.connect(
            dbname=postgres_db,
            user=postgres_user,
            password=postgres_password,
            host=postgres_host,
            port=postgres_port
        )
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                feedback VARCHAR(10) CHECK (feedback IN ('positive', 'negative')) NOT NULL,
                comments TEXT,
                title TEXT,
                link TEXT,
                date_time TIMESTAMP NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bad_responses (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                raw_response TEXT NOT NULL,
                error TEXT,
                date_time TIMESTAMP NOT NULL
            );
        """)

        conn.commit()
        print("Tables created successfully!")

    except Exception as e:
        print(f"Error while setting up the database: {str(e)}")

    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

# Call the init_db function to set up the table
init_db()