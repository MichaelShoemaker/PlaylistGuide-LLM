import os
import ollama
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
    return [
    {
        'title': record['_source']['title'],
        'timecode_text': record['_source']['timecode_text'],
        'link': record['_source']['link'],
        'text': record['_source']['text'] 
        
    }
    for record in response["hits"]["hits"]
    ]


    # Use Ollama to generate an answer
def ask_ollama(prompt):
    response = ollama.chat(model='llama3', messages=[
    {
        'role': 'user',
        'content': f"{prompt}",
    },
    ])
    return response['message']['content']

def make_context(question, records):
    return f"""
        You are a helpful program which is given a quesion and then the results from video transcripts which should answer the question given.
        This is an online course about using Retreival Augmented Generation (RAGS) and LLMs as well as how to evaluate the results of elasticsearch
        and the answers from the LLMs, how to monitor the restults etc. In the Course we used MAGE as an Orchestrator and PostgreSQL to capture user
        feedback. Given the question below, look at the records in the RECORDS section and return the best matching video link and a short summary
        and answer if you are able to which will answer the students question.

        QUESTION:
        {question}

        RECORDS:
        {records}
        """

def get_answer(question):
    ask_ollama(make_context(question, multi_search(question)))
    try:
        answer = ask_ollama()
    except Exception as e:
        st.error(f"Error during Ollama completion: {e}")
        answer = ""



# Perform search and display results
if st.button("Search"):
    if question:
        results = get_answer(question)
        
        st.write("### Relevant Video Links:")
        # for result in results:
        #     title = result['title']
        #     timecode = result['timecode_text']
        #     link = result['link']
            
        #     # Display title, timecode, and clickable link with proper formatting
        #     st.markdown(f"**Title**: {title}")
        #     st.markdown(f"**Timecode**: {timecode}")
        #     st.markdown(f"[Watch here]({link})")
        #     st.write("---")  # Separator for each result

        # Feedback section
        st.write("Was this result helpful?")
        feedback = ''
        if st.button("👍 Yes"):
            st.write("Thank you for your feedback!")
            feedback = 'positive'
        elif st.button("👎 No"):
            st.write("Thank you for your feedback!")
            feedback = 'negative'

        # # Store feedback in PostgreSQL
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
            """, (question, results, feedback, datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            st.error(f"Error during feedback submission: {e}")
