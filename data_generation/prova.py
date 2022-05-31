import json
import spacy
from add_context import get_salient_type
from transformers import pipeline

with open('lama/data/Squad/test.jsonl') as f:
    data = [json.loads(line) for line in f]

nlp = spacy.load("en_core_web_sm")
all_stopwords = nlp.Defaults.stop_words

unmasker = pipeline('fill-mask', model='roberta-base', tokenizer="roberta-base", top_k=20)

for i, d in enumerate(data[6:]):
    print(f"Processing sentence {i}")
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

            if type_of_text_input is None:
                print("No type found")
                continue

            print(f"Type of {text}: {type_of_text_input}")

            # In Squad dataset masks are defined as [MASK], but huggingface BERT needs <mask>
            d['masked_sentences'][0] = d['masked_sentences'][0].replace("[MASK]", "<mask>")

            sentence_to_verify_with_context = f"{text} is a {type_of_text_input}. {d['masked_sentences'][0]}"

            token_guesses_with_context = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                                     unmasker(sentence_to_verify_with_context)))

            token_guesses_without_context = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                                  unmasker(d['masked_sentences'][0])))

            true_label = d['obj_label'].lower()
            print(f"True label: {true_label}")
            print(sentence_to_verify_with_context)
            print(token_guesses_with_context)
            print(f"{'found' if true_label in token_guesses_with_context else 'not found'}")
            print()
            print(d['masked_sentences'][0])
            print(token_guesses_without_context)
            print(f"{'found' if true_label in token_guesses_without_context else 'not found'}")
            print("-"*30)
