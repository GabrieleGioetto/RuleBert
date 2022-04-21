from src.Rule import Rule
from src.Triple import Triple

from transformers import pipeline
import argparse
import pickle

my_parser = argparse.ArgumentParser(description='Get evidence with BERT')

my_parser.add_argument('--rule',
                       type=str,
                       help='Rule')

my_parser.add_argument('--support',
                       type=float,
                       help='Support')

my_parser.add_argument('--claim',
                       type=str,
                       help='Claim')


args = my_parser.parse_args()

rule_text = args.rule  # String of the rule (Ex. "relation(A,B) :- something(A,B)")
rule_support = args.support  # String of the rule
claim_text = args.claim

claim = Triple(claim_text)
print(claim.get_sentence(claim.subject, claim.object))

rule = Rule(rule=rule_text)
rule.set_rule_support(rule_support)

rule.add_rule_info(rule_text)

with open('data_generation/data/rule2text.pkl', 'rb') as f:
    rule2text = pickle.load(f)

rule_in_english = rule2text[rule_text]

unmasker = pipeline('fill-mask', model='roberta-base', tokenizer="roberta-base")


# This is only with one rule, it must be extended for all rules in a list
if claim.relation in list(map(lambda t: t.relation, rule.triples)):

    # I assume claim is present only once in the rule
    claim_in_rule = list(filter(lambda t: t.relation == claim.relation, rule.triples))[0]

    for triple in rule.triples:
        # I iterate over all triplets in the rule which are different then the one in the claim
        # If they have a subset of the variables in the claim
        if triple.relation != claim.relation and set(triple.subject_list).issubset(set(claim_in_rule.subject_list)):
            # BERT
            triple_text_without_subject = triple.get_sentence("<mask>", claim.object)
            triple_text_without_object = triple.get_sentence(claim.subject, "<mask>")

            print(triple_text_without_subject)
            print(triple_text_without_object)
            print(unmasker(triple_text_without_subject))
            print(unmasker(triple_text_without_object))

