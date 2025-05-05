# Python program to generate word vectors using Word2Vec

# importing all necessary modules
from gensim.models import Word2Vec
from gensim.models.phrases import Phrases, Phraser
from nltk.tokenize import sent_tokenize, word_tokenize
import warnings
import nltk
nltk.data.path.append('C:\\Users\\seanh\\AppData\\Roaming\\nltk_data')
nltk.download('punkt_tab')

warnings.filterwarnings(action='ignore')

# Reads ‘alice.txt’ file
with open("C:\\Users\\seanh\\Documents\\University\\CAPSTONE 2\\src\\data\\stafF_profiles.csv", encoding="utf-8") as sample:
    s = sample.read()

# Replaces escape character with space
f = s.replace("\n", " ").replace("[", " ").replace("]", " ").replace("\"", " ").replace("\'", " ").replace(",", " ")

data = []

# iterate through each sentence in the file
for i in sent_tokenize(f):
	temp = []

	# tokenize the sentence into words
	for j in word_tokenize(i):
		temp.append(j.lower())

	data.append(temp)

# Detect and combine multi-word phrases
phrases = Phrases(data, min_count=1, threshold=1)  # Adjust min_count and threshold as needed
bigram = Phraser(phrases)
data = [bigram[sentence] for sentence in data]

# Create CBOW model
model1 = Word2Vec(data, min_count=1, vector_size=100, window=5)

# Check if words exist in the vocabulary before querying
if "machine_learning" in model1.wv and "artificial intelligence" in model1.wv:
    print("Cosine similarity between 'machine_learning' and 'artificial intelligence' - CBOW : ",
          model1.wv.similarity('machine_learning', 'artificial_intelligence'))
else:
    print("'machine_learning' or 'artificial intelligence' not in vocabulary")

if "machine_learning" in model1.wv and "machines" in model1.wv:
    print("Cosine similarity between 'machine_learning' and 'machines' - CBOW : ",
          model1.wv.similarity('machine_learning', 'machines'))
else:
    print("'machine_learning' or 'machines' not in vocabulary")

# Create Skip Gram model
model2 = Word2Vec(data, min_count=1, vector_size=100, window=5, sg=1)

if "machine_learning" in model2.wv and "artificial intelligence" in model2.wv:
    print("Cosine similarity between 'machine_learning' and 'artificial intelligence' - Skip Gram : ",
          model2.wv.similarity('machine_learning', 'artificial_intelligence'))
else:
    print("'machine_learning' or 'artificial intelligence' not in vocabulary")

if "machine_learning" in model2.wv and "machines" in model2.wv:
    print("Cosine similarity between 'machine_learning' and 'machines' - Skip Gram : ",
          model2.wv.similarity('machine_learning', 'machines'))
else:
    print("'machine_learning' or 'machines' not in vocabulary")