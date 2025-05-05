from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from nltk.tokenize import word_tokenize
import csv

# Read the CSV file and extract relevant fields as documents
data = []
with open("data\\staff_profiles.csv", mode="r", encoding="utf-8") as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        # Combine relevant fields into a single document
        document = " | ".join([
            section for section in [
                # row.get("biography", "").replace("[", "").replace("]", "").replace("'", "").strip(),
                row.get("academic_and_professional_qualifications", "").replace("[", "").replace("]", "").replace("'", "").strip().lower(),
                row.get("research_interests", "").replace("[", "").replace("]", "").replace("'", "").strip().lower(),
                row.get("teaching_areas", "").replace("[", "").replace("]", "").replace("'", "").strip().lower(),
                row.get("courses_taught", "").replace("[", "").replace("]", "").replace("'", "").strip().lower(),
                # row.get("notable_publications", "").replace("[", "").replace("]", "").replace("'", "").strip()
            ] if section and section != "N/A"  # Exclude empty or "N/A" sections
        ])
        data.append(document)

# Preprocess the documents and create TaggedDocuments
tagged_data = [
    TaggedDocument(words=word_tokenize(doc.lower()), tags=[str(i)])
    for i, doc in enumerate(data)
]

# Train the Doc2Vec model
model = Doc2Vec(vector_size=30, min_count=2, epochs=100) #need to go through iterations
model.build_vocab(tagged_data)
model.train(tagged_data, total_examples=model.corpus_count, epochs=model.epochs)

# Save and reload the model
model.save("data\\d2v.model")
model = Doc2Vec.load("data\\d2v.model")

# Find the most similar document to the first document
similar_doc = model.dv.most_similar('0')  # Find the most similar document to document 0
most_similar_tag = similar_doc[0][0]  # Get the tag of the most similar document

# Print the original and matching document text
print(f"Original Document (Document 0):\n{data[0]}\n")
print(f"Most Similar Document (Document {most_similar_tag}):\n{data[int(most_similar_tag)]}\n")
print(f"Similarity Score: {similar_doc[0][1]}")

similar_word = model.wv.most_similar(positive=['artificial', 'intelligence', 'machine'])
print(similar_word)

# Get the document vectors
document_vectors = [
    model.infer_vector(word_tokenize(doc.lower())) for doc in data
]

# Print the document vectors (optional)
# for i, doc in enumerate(data):
#     print(f"Document {i+1}: {doc}")
#     print(f"Vector: {document_vectors[i]}")
#     print()