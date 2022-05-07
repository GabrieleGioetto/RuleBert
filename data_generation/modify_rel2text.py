import json
import pickle

# Opening JSON file
with open('rel2text.json') as json_file:
    data = json.load(json_file)

    # for reading nested data [0] represents
    # the index value of the list
    print("Type:", type(data))

    with open('data/rel2text_extra_word.pkl', 'wb') as f:
        pickle.dump(data, f)
