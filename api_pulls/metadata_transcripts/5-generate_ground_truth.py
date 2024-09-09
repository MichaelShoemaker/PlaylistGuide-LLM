import os
import ast
from dotenv import load_dotenv
import ollama
from openai import OpenAI
import pickle

load_dotenv()

# Retrieve the OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")


def make_prompt(transcript):
    return f"""
You are an expert at generating potential questions based on course content. This course teaches Retrieval Augmented Generation (RAG) and Large Language 
Models (LLMs). Please generate three potential questions a student might ask, specifically where the given record would be the most relevant to provide 
answers. Return the original dictionary with a new field 'student_questions' added. The field should contain a list of three questions as 
'student_questions': [question1, question2, question3]. Return the dictionary in JSON format. Not python. JSON format and just return the dictionary
in JSON FORMAT

Here is the record for which to generate the questions:

DICTIONARY:
{transcript}
"""


client = OpenAI()
def make_recs(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    # Extract response content
    response_content = response.choices[0].message

    # Optionally, print or process the response
    return response_content

with open('elastic_search_data.pkl', 'rb') as infile:
    transcripts = pickle.load(infile)

for transcript in transcripts:
    transcript.pop('search_vector', None) 

#Make prompts for OpenAI
prompts = []
for transcript in transcripts:
    prompts.append(make_prompt(transcript))

with open('prompts_for_OpenAI.pkl', 'wb') as outfile:
    pickle.dump(prompts, outfile)


responses = []
for prompt in prompts:
    responses.append(make_recs(prompt))

with open('OpenAI_responses.pkl', 'wb') as outfile:
    pickle.dump(responses, outfile)

contents = []
for response in responses:
    contents.append(response.content)

# def fix_dict_prompt(broken_dict):
#     return f"""
#     Can you format this into a proper python dictionary and just return it as a dictionary? Return JUST THE DICTIONARY without any extra words:
#     I don't want anything except the dictionary I don't want code blocks with ```. Just the formatted dictionary. Additionally can you remove any single or
#     double quotes and commas in the values which may cause issues when using ast.literal_eval?

#     {broken_dict}
#     """


# def ask_ollama(prompt):
#     response = ollama.chat(model='llama3', messages=[
#     {
#         'role': 'user',
#         'content': f"{prompt}",
#     },
#     ])
#     return response['message']['content']

# to_evaluate = []
# for record in contents:
#     to_evaluate.append(ask_ollama(record))

# with open('to_evaluate.pkl', 'wb') as outfile:
#     pickle.dump(to_evaluate, outfile)

# bad_parses = []
# ground_truth_recs = []
# for eval in to_evaluate:
#     try:
#         ground_truth_recs(ast.literal_eval(eval))
#     except Exception as e:
#         bad_parses.append(eval)

# with open('ground_truth.pkl', 'wb') as outfile:
#     pickle.dump(ground_truth_recs, outfile)

# print(len(bad_parses))

# with open('error_records.pkl', 'wb') as outfile:
#     pickle.dump(bad_parses, outfile)