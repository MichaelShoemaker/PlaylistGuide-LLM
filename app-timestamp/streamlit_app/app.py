import os
# import ollama
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


    # Use Ollama to generate an answer
# def ask_ollama(prompt):
#     try:
#         # Send request to Ollama API with api_key
#         response = ollama.chat(
#             model='llama3', 
#             messages=[
#                 {
#                     'role': 'user',
#                     'content': prompt,
#                 },
#             ],
#             # api_key='ollama'  # Adding the api_key here
#         )
#     except Exception as e:
#         return f"Error running ollama {str(e)}"
#     return response['message']['content']
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



# Perform search and display results
if st.button("Search"):
    if question:
        results = get_answer(question)
        st.write("I believe you are looking for this video")
        st.write("### Relevant Video Links:")
        # Display the relevant video content
        st.write('Summary:')
        st.write(results.content['summary'])
        st.write('Title:')
        st.write(results.content['title'])
        st.write('Link:')
        st.write(results.content['link'])


        # Feedback section
        st.write("Was this result helpful?")
        feedback = ''
        if st.button("👍 Yes"):
            st.write("Thank you for your feedback!")
            feedback = 'positive'
        elif st.button("👎 No"):
            st.write("Thank you for your feedback!")
            feedback = 'negative'

        # Comment field for users
        st.write("Any additional comments?")
        comments = st.text_area("Enter your comments here")

        # Insert data into PostgreSQL
        try:
            conn = psycopg2.connect(
                dbname=postgres_db,
                user=postgres_user,
                password=postgres_password,
                host=postgres_host,
                port=postgres_port
            )
            cursor = conn.cursor()

            # Capture all fields from the `results` dictionary
            cursor.execute("""
                INSERT INTO feedback (question, answer, feedback, comments, title, timecode_text, link, date_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                question,  # The original question from the user
                results.get('content'),  # The content returned from the model
                feedback,  # Positive or negative feedback
                comments,  # User comments entered in the text area
                results.get('title'),  # Title from the `results` dictionary
                results.get('timecode_text'),  # Timecode from the `results` dictionary
                results.get('link'),  # Link from the `results` dictionary
                datetime.now()  # Timestamp for the feedback
            ))

            conn.commit()
            cursor.close()
            conn.close()
            st.success("Feedback submitted successfully!")
        except Exception as e:
            st.error(f"Error during feedback submission: {e}")