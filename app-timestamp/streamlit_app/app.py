import os
from dotenv import load_dotenv
import streamlit as st
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import openai
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
postgres_db = os.getenv("POSTGRES_DB", "transcripts")
postgres_host = os.getenv("POSTGRES_HOST", "db")
postgres_port = os.getenv("POSTGRES_PORT", "5432")

# Initialize connections
es = Elasticsearch(elasticsearch_url)
model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')
openai.api_key = openai_api_key

# Initialize PostgreSQL database with required table
def init_db():
    conn = psycopg2.connect(
        dbname=postgres_db,
        user=postgres_user,
        password=postgres_password,
        host=postgres_host,
        port=postgres_port
    )
    cursor = conn.cursor()
    
    # Create the table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            question TEXT,
            answer TEXT,
            feedback VARCHAR(10),
            date_time TIMESTAMP
        );
    """)
    
    # Ensure the sequence exists and adjust it if necessary
    cursor.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'feedback_id_seq') THEN
                CREATE SEQUENCE feedback_id_seq START 1;
            END IF;
        END $$;
    """)
    
    conn.commit()
    cursor.close()
    conn.close()


# Call the init_db function to set up the table
init_db()

# Streamlit app setup
st.title("YouTube Transcript Search with OpenAI")

# Get user input
question = st.text_input("Ask a question about the YouTube videos")

# Function to perform Elasticsearch search and interact with OpenAI
def search_and_answer(question):
    vector_search_term = model.encode(question)#.tolist()
def knn_query(question):
    return  {
        "field": "text_vector",
        "query_vector": model.encode(question),
        "k": 5,
        "num_candidates": 10000,
        "boost": 0.5,
        
    }

def keyword_query(question):
    return {
        "bool": {
            "must": {
                "multi_match": {
                    "query": f"{question}",
                    "fields": ["description^3", "text", "title"],
                    "type": "best_fields",
                    "boost": 0.5,
                }
            },
        }
    }

def multi_search(key_word):
    response = es.search(
        index='video-content',
        query=keyword_query(key_word),
        knn=knn_query(key_word),
        size=10
    )
    response["hits"]["hits"]
    # # try:
    # #     res = es.search(index="video-content", body=query)
    # try:
    #     multi_search(question)
    # except Exception as e:
    #     st.error(f"Error during Elasticsearch query: {e}")
    #     return "", []

    search_results = multi_search(question)

    # Compile context from search results
    context = "\n".join([hit["_source"]["text"] for hit in search_results])
    links = [hit["_source"]["link"] for hit in search_results]

    # Use OpenAI to generate an answer
    # try:
    #     response = openai.Completion.create(
    #         engine="davinci",
    #         prompt=f"Question: {question}\nContext: {context}\nAnswer:",
    #         max_tokens=150
    #     )
    #     answer = response["choices"][0]["text"].strip()
    # except Exception as e:
    #     st.error(f"Error during OpenAI completion: {e}")
    #     answer = ""
    answer = context
    return answer, links

# Perform search and display results
if st.button("Search"):
    if question:
        answer, links = multi_search(question)
        # st.write("Answer from OpenAI:")
        # st.write(answer)
        st.write("Relevant Video Links:")
        for link in links:
            st.write(link)
        st.write("Was this answer helpful?")
        feedback = ''
        if st.button("👍 Yes"):
            st.write("Thank you for your feedback!")
            feedback = 'positive'
        elif st.button("👎 No"):
            st.write("Thank you for your feedback!")
            feedback = 'negative'

        # Store feedback in PostgreSQL
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
                INSERT INTO feedback (question, answer, feedback, date_time)
                VALUES (%s, %s, %s, %s)
            """, (question, answer, feedback, datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            st.error(f"Error during feedback submission: {e}")
