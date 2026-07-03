import nltk
from nltk.tokenize import RegexpTokenizer

def get_tokens(text):
    pattern = r'\S*[A-Za-z]\S*'
    tokenizer = RegexpTokenizer(pattern)
    tokens = tokenizer.tokenize(text)
    return tokens
