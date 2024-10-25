import os
import redis
import json
from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import openai
import psycopg2
import numpy as np
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



# Connect to Redis
r = redis.Redis(host='redis', port=6379, db=0)

# Tokenize the question using SentenceTransformer
def get_embedding(text):
    return model.encode(text).tolist()

# Retrieve the closest match in Redis
def check_redis_for_similar_question(question_embedding):
    # Ensure the question_embedding is a list of floats
    question_embedding = [float(x) for x in question_embedding]

    # Iterate through all keys (representing previous questions) in Redis
    for key in r.scan_iter():
        # Decode the key from bytes to a string
        key = key.decode("utf-8")

        # Retrieve the stored embedding from Redis
        stored_data = r.get(key)
        
        if stored_data is None or not stored_data.strip():
            continue  # Skip if there is no stored data or it's empty
        
        # Load the stored data and check if it has an embedding field
        try:
            stored_data = json.loads(stored_data)
            # If stored_data is a dictionary, extract 'embedding'; otherwise assume it's the embedding itself
            stored_embedding = stored_data.get("embedding", []) if isinstance(stored_data, dict) else stored_data
            # Ensure stored_embedding is a list of floats with the correct shape
            if not isinstance(stored_embedding, list) or len(stored_embedding) != len(question_embedding):
                print(f"Skipping key '{key}': embedding has an incorrect format or length")
                continue
            stored_embedding = [float(x) for x in stored_embedding]
        except (json.JSONDecodeError, TypeError):
            print(f"Skipping key '{key}': invalid format")
            continue
        
        # Compare cosine similarity between the question and stored embeddings
        try:
            similarity = np.dot(stored_embedding, question_embedding) / (
                np.linalg.norm(stored_embedding) * np.linalg.norm(question_embedding)
            )
            if similarity > 0.8:  # Similarity threshold
                cached_response = r.get(f"{key}_response")
                if cached_response is not None:
                    return json.loads(cached_response)
        except Exception as e:
            print(f"Error calculating similarity for key '{key}': {e}")
            continue
    
    return None

def save_to_redis(question, question_embedding, response):
    # Store the question and embedding in a structured format
    data = {
        "embedding": question_embedding,
        "question": question
    }
    r.set(question, json.dumps(data))
    r.set(f"{question}_response", json.dumps(response))





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
def ask_openai(prompt, mode):
        if mode == 'prod':
            response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"{prompt}"}
            ],
            temperature=0.7
        )
            response_content = response.choices[0].message.content

            return response_content
        elif mode == 'test':
            return 'My test response'
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
    # Step 1: Get the embedding for the question
    question_embedding = get_embedding(question)
    
    # Step 2: Check if a similar question already exists in Redis
    cached_response = check_redis_for_similar_question(question_embedding)
    
    if cached_response:
        # Return cached response if found
        st.write("Returning cached response from Redis.")
        return cached_response
    else:
        # Perform multi-search (stubbed for simplicity)
        search_results = multi_search(question)
        
        # Step 3: Create the prompt and call OpenAI API
        prompt = make_context(question, search_results)
        
        try:
            answer = ask_openai(prompt, 'prod')
            # Step 4: Cache the question, embedding, and response in Redis
            save_to_redis(question, question_embedding, answer)
        except Exception as e:
            st.error(answer)
            st.error(f"Error during OpenAI completion: {e} your API key is set to {openai_api_key}")
            answer = {}
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
        response = json.loads(results) if isinstance(results, str) else results
    except json.JSONDecodeError as e:
        st.write(f"Error decoding JSON: {str(e)}")
        st.write(results) 
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
