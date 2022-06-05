import pickle

with open('rel2text.pkl', 'rb') as f:
    data = pickle.load(f)

data["almamater"] = "the alma mater of !!S!! is !!O!!."

with open('rel2text.pkl', 'wb') as f:
    pickle.dump(data, f)


with open('rel2text_extra_word.pkl', 'rb') as f:
    data = pickle.load(f)

data["almamater"] = "the alma mater of !!S!! is !!O!!."

with open('rel2text_extra_word.pkl', 'wb') as f:
    pickle.dump(data, f)