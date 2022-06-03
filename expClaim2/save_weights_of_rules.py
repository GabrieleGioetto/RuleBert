import pickle
import os
import json

with open('data_generation/data/rule2text.pkl', 'rb') as f:
    rule2text = pickle.load(f)

sub_folders_walk = os.walk("data/")

sub_folders = []
for sub_folder in sub_folders_walk:
    sub_folders.append(sub_folder)

sub_folders = dict(map(lambda x: (x[0].split("/")[-1], x[0]), sub_folders))

print(len(sub_folders))

number_of_rules = len(rule2text)
counter_found_rules = 0
for rule in rule2text:
    if rule in sub_folders.keys():
        counter_found_rules += 1

        with open(sub_folders[rule], 'r') as json_file:
            json_list = list(json_file)

        weight = json_list[0]["rule_support"]

print(f"counter_found_rules: {counter_found_rules}")


