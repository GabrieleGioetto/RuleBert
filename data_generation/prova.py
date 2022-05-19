import json
import spacy
from add_context import get_salient_type


with open('lama/data/Squad/test.jsonl') as f:
    data = [json.loads(line) for line in f]

nlp = spacy.load("en_core_web_sm")
all_stopwords = nlp.Defaults.stop_words

for d in data[:5]:
    sentence = nlp(d["masked_sentences"][0])
    for ent in sentence.ents:
        if ent.label_ in ["EVENT", "PERSON", "ORG"]:
            print(ent.text, ent.label_, type(ent.label_))
            text = []
            for token in ent.text.split():
                if token.lower() not in all_stopwords:  # checking whether the word is not
                    text.append(token)  # present in the stopword list.

            text = " ".join(text)
            type_of_text_input = get_salient_type(text)

            print(f"Type of {text}: {type_of_text_input}")
