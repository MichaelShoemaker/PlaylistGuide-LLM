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
postgres_db = os.getenv("POSTGRES_DB", "feedback")
postgres_host = os.getenv("POSTGRES_HOST", "db")
postgres_port = os.getenv("POSTGRES_PORT", "5432")

# Initialize connections
es = Elasticsearch(elasticsearch_url)
model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')


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
    search_results = multi_search(question)
    prompt = make_context(question,search_results)
    try:
        answer = ask_openai(prompt)
    except Exception as e:
        st.error(f"Error during Ollama completion: {e} your api key is set to {openai_api_key}")
        answer = ""
    return answer


def display_response(response):
    st.markdown(f"### Video Title: {response['title']}")
    st.markdown(f"**Summary**: {response['summary']}")
    st.markdown(f"[Watch Video]({response['link']})")

# Check if 'response' exists in session state, if not, initialize it
if 'response' not in st.session_state:
    st.session_state.response = None

# Check if 'feedback_submitted' exists in session state, if not, initialize it
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False

# Perform search and display results
if st.button("Search"):
    # Simulating response for testing purposes
    results = get_answer(question)
    
    try:
         # Check if results.content is a JSON string and parse it
        response = json.loads(results.content) if isinstance(results.content, str) else results.content
    except json.JSONDecodeError as e:
        st.write(f"Error decoding JSON: {str(e)}")
        st.write(results.content) 
    st.session_state.response = response
    st.session_state.feedback_submitted = False  # Reset feedback on new search

# Display response if available in session state
if st.session_state.response:

    display_response(st.session_state.response)

    if not st.session_state.feedback_submitted:
        st.write("Was this result helpful?")
        
        # Handle feedback buttons and update session state
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍 Yes"):
                st.session_state.feedback = 'positive'
                st.session_state.feedback_submitted = True  # Mark feedback as submitted
        with col2:
            if st.button("👎 No"):
                st.session_state.feedback = 'negative'
                st.session_state.feedback_submitted = True  # Mark feedback as submitted

    # Show feedback result if submitted
    if st.session_state.feedback_submitted:
        st.write(f"Captured Feedback: {st.session_state.feedback}")

    # Comment field for users
    comments = st.text_area("Enter your comments here")
    if comments:
        st.write(f"Captured Comments: {comments}")
    
    # Insert data into PostgreSQL only if feedback is provided and submission is complete
    if st.session_state.feedback_submitted:
        try:
            # Connect to PostgreSQL database
            conn = psycopg2.connect(
                dbname=postgres_db,
                user=postgres_user,
                password=postgres_password,
                host=postgres_host,
                port=postgres_port
            )
            st.write("Database connection successful")
            cursor = conn.cursor()

            try:
                # Retrieve the response from session state
                response = st.session_state.response

                # Insert into `feedback` table
                cursor.execute("""
                    INSERT INTO feedback (question, answer, feedback, comments, title, link, date_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    question,  # The original question from the user
                    response.get('summary', ''),  # Extract summary from the parsed response
                    st.session_state.feedback,  # Positive or negative feedback
                    comments,  # User comments entered in the text area
                    response.get('title', ''),  # Title from the `response` dictionary
                    response.get('link', ''),  # Link from the `response` dictionary
                    datetime.now()  # Timestamp for the feedback
                ))

                conn.commit()
                st.success("Feedback submitted successfully!")

            
            except Exception as e:
                # Log error if something goes wrong with insertion
                st.error(f"Error while inserting feedback: {str(e)}")
                
                # Insert into `bad_responses` if an error occurred
                cursor.execute("""
                    INSERT INTO bad_responses (question, raw_response, error, date_time)
                    VALUES (%s, %s, %s, %s)
                """, (
                    question,  # The original question from the user
                    str(st.session_state.response),  # The raw response that couldn't be parsed
                    str(e),  # The error message
                    datetime.now()  # Timestamp for the bad response
                ))
                conn.commit()
            
            finally:
                cursor.close()
                conn.close()
                st.write("Database connection closed")
        
        except Exception as e:
            st.error(f"Error during feedback submission: {e}")
                        # JavaScript to reload the page
        st.write("""
            <script>
            setTimeout(function() {
                window.location.reload();
            }, 1500);  // 1.5 seconds delay before reload
            </script>
        """, unsafe_allow_html=True)