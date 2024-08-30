import pickle
import hashlib
from openai import OpenAI
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

def create_dataset():
    with open('transcripts_metadata_records.pkl', 'rb') as infile:
        return pickle.load(infile)



def gen_ids(data):
    for rec in data:
        unique_id = rec['vid_id'].strip()+rec['timecode'].strip()
        hash_object = hashlib.md5(unique_id.encode())
        hash_hex = hash_object.hexdigest()
        rec['id'] = hash_hex
        rec['text_vector'] = rec['title']+' '+rec['text']+' '+rec['description']
    return data


def add_vectors(data):
    for rec in data:
        rec['search_vector'] = model.encode(rec['text_vector'])
    return data




data = create_dataset()
data_ids = gen_ids(data)
load_data = add_vectors(data_ids)

for i in load_data:
    if '5' in i['title']:
        print(i['title'])

with open('elastic_search_data.pkl', 'wb') as outfile:
    pickle.dump(load_data, outfile)




# prompt = """
# You are a system that generates potential questions based on the idea that there is an Online course which teached Retrieval Augmented Generation (RAG)
# and using Large Language Models to improve the accuracy of using LLMs. Determining metrics for measuring performance of RAG and LLM answers. The following
# are records in the RAG system. For each record, please generate a three potential questions a student might ask where the record in question would be the 
# best record to be returned. Again, look at all of the records to assist you in determining the questions to ask where the current record would be the best
# answer to be returned. Please return your responses in JSON format where 
# """


# client = OpenAI()

# def add_keywords(data, prompt):
#     completion = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": f"{prompt}"},
#             {
#                 "role": "user",
#                 "content": f"{data}"
#             }
#         ]
#     )

#     return completion.choices[0].message