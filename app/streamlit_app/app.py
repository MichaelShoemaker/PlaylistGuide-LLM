import os
# import ollama
import json
from openai import OpenAI
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


# Initialize PostgreSQL database with required table
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
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback VARCHAR(10) CHECK (feedback IN ('positive', 'negative')) NOT NULL,
            comments TEXT,
            title TEXT,
            timecode_text TEXT,
            link TEXT,
            vector_field VARCHAR(50),  -- Add vector field column
            date_time TIMESTAMP NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bad_responses (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            raw_response TEXT NOT NULL,
            date_time TIMESTAMP NOT NULL
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()

# Call the init_db function to set up the table
init_db()

st.title("YouTube Transcript Search with OpenAI")

# Get user input
question = st.text_input("Ask a question about the YouTube videos")

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

def knn_query(question, selected_field):
    return  {
        "field": selected_field,  # Use the selected field from the dropdown
        "query_vector": model.encode(question),
        "k": 5,
        "num_candidates": 10000,
        "boost": 0.5,
    }

def multi_search(key_word, selected_field):
    response = es.search(
        index='video-content',
        query=keyword_query(key_word),
        knn=knn_query(key_word, selected_field),  # Pass the selected vector field to the KNN query
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

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()
def ask_openai(prompt):
        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"{prompt}"}
        ],
        temperature=0.7
    )

    # Extract response content
        response_content = response.choices[0].message

        # Optionally, print or process the response
        return response_content
def make_context(question, records):
    return f"""
        You are a helpful program which is given a quesion and then the results from video transcripts which should answer the question given.
        This is an online course about using Retreival Augmented Generation (RAGS) and LLMs as well as how to evaluate the results of elasticsearch
        and the answers from the LLMs, how to monitor the restults etc. In the Course we used MAGE as an Orchestrator and PostgreSQL to capture user
        feedback. Given the question below, look at the records in the RECORDS section and return the best matching video link and a short summary
        and answer if you are able to which will answer the students question. Again your response should be a link from the records in the RECORDS
        section below. 

        Please return your answer as a dictionary without json```. Just have summary, title and link as as keys in the dictionary.

        QUESTION:
        {question}

        RECORDS:
        {records}
        """

def get_answer(question):
    # Pass the selected vector field to the multi_search function
    search_results = multi_search(question, vector_field)  # Pass vector_field from the dropdown
    prompt = make_context(question, search_results)
    
    try:
        answer = ask_openai(prompt)
    except Exception as e:
        st.error(f"Error during OpenAI completion: {e} your api key is set to {openai_api_key}")
        answer = ""
    
    return answer


def display_response(response):
    st.markdown(f"### Video Title: {response['title']}")
    st.markdown(f"**Summary**: {response['summary']}")
    st.markdown(f"[Watch Video]({response['link']})")

# Add a dropdown to select the vector field
vector_field = st.selectbox(
    "Select the vector field for Elasticsearch search:",
    ['timecode_vector', 'text_vector']
)
 # Initialize session state for feedback and response
if "feedback" not in st.session_state:
    st.session_state.feedback = None
if "response_shown" not in st.session_state:
    st.session_state.response_shown = False
    
# Perform search and display results
if st.button("Search"):
    if question:
        results = get_answer(question)
        
        try:
            # Check if results.content is a JSON string and parse it
            response = json.loads(results.content) if isinstance(results.content, str) else results.content
        except json.JSONDecodeError as e:
            st.write(f"Error decoding JSON: {str(e)}")
            st.write(results.content)  # Show the raw content for debugging
        except Exception as e:
            st.write(f"Unexpected error: {str(e)}")
            st.write(results.content)

        if isinstance(response, dict):
            display_response(response)
        else:
            st.write("Response is not in the expected format.")
            

if st.session_state.response_shown:
    st.write("Was this result helpful?")
    
    if st.button("👍 Yes"):
        st.write("Thank you for your feedback!")
        st.session_state.feedback = 'positive'
    elif st.button("👎 No"):
        st.write("Thank you for your feedback!")
        st.session_state.feedback = 'negative'

    # Insert data into PostgreSQL only if feedback is provided
    if st.session_state.feedback is not None:
        try:
            conn = psycopg2.connect(
                dbname=postgres_db,
                user=postgres_user,
                password=postgres_password,
                host=postgres_host,
                port=postgres_port
            )
            cursor = conn.cursor()

            try:
                # Insert into `feedback` table with the selected vector field
                cursor.execute("""
                    INSERT INTO feedback (question, answer, feedback, title, timecode_text, link, vector_field, date_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    question,  # The original question from the user
                    response.get('summary', ''),  # Extract summary from the parsed response
                    st.session_state.feedback,  # Positive or negative feedback from session state
                    response.get('title', ''),  # Title from the `response` dictionary
                    response.get('timecode_text', ''),  # Timecode from the `response` dictionary
                    response.get('link', ''),  # Link from the `response` dictionary
                    vector_field,  # Store the selected vector field
                    datetime.now()  # Timestamp for the feedback
                ))
            except (json.JSONDecodeError, TypeError) as e:
                # If response is not valid JSON or there's a TypeError, insert into `bad_responses`
                cursor.execute("""
                    INSERT INTO bad_responses (question, raw_response, date_time)
                    VALUES (%s, %s, %s)
                """, (
                    question,  # The original question from the user
                    results.content,  # The raw response that couldn't be parsed
                    datetime.now()  # Timestamp for the bad response
                ))

            conn.commit()
            cursor.close()
            conn.close()
            st.success("Feedback submitted successfully!")
        except Exception as e:
            st.error(f"Error during feedback submission: {e}")
