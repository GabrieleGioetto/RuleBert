from typing import List

from src.Rule import Rule
from src.Triple import Triple

from transformers import pipeline
import argparse
import pickle

from collections import defaultdict

my_parser = argparse.ArgumentParser(description='Get evidence with BERT')

# my_parser.add_argument('--rule',
#                        type=str,
#                        help='Rule')

my_parser.add_argument('--support',
                       type=float,
                       help='Support')

my_parser.add_argument('--claim',
                       type=str,
                       help='Claim')

args = my_parser.parse_args()

# rule_text = args.rule  # String of the rule (Ex. "relation(A,B) :- something(A,B)")
rule_support = args.support  # String of the rule
claim_text = args.claim

claim = Triple(claim_text)
print(claim.get_sentence(claim.subject, claim.object, extra_word=True))

# rule = Rule(rule=rule_text)
# rule.set_rule_support(rule_support)
#
# rule.add_rule_info(rule_text)

with open('data_generation/data/rule2text.pkl', 'rb') as f:
    rule2text = pickle.load(f)

# rule_in_english = rule2text[rule_text]

unmasker = pipeline('fill-mask', model='roberta-base', tokenizer="roberta-base", top_k=20)


def common_member(triple: Triple, claim: Triple):
    triple_set = set(triple)
    claim_set = set(claim)
    if len(triple_set.intersection(claim_set)) > 0:
        diff = triple_set.difference(claim_set)
        if diff:
            return list(diff)[0]
    return False


# Loop over all rules saved locally
for rule_key in rule2text:
    # check if in current rule there is the relation we are trying to verify the trueness
    if claim.relation in rule_key:
        rule = Rule(rule=rule_key)
        rule.set_rule_support(rule_support)
        rule.add_rule_info(rule_key)

        # TODO: to implement better
        # to avoid neg relations ( I look for founder, I find negfounder)
        if claim.relation not in rule.relations:
            continue

        # I assume claim relation is present only once in the rule
        claim_in_rule = list(filter(lambda t: t.relation == claim.relation, rule.triples))[0]

        variables_not_known = defaultdict(list)

        for triple in rule.triples:
            # I iterate over all triplets in the rule which are different then the one in the claim
            # If they have a subset of the variables in the claim
            # if triple.relation != claim.relation and set(triple.subject_list).issubset(set(claim_in_rule.subject_list)):

            if triple.relation != claim.relation:

                # case in which in the triple we know both variables
                if triple.vars == claim_in_rule.vars:
                    # add that if the triple is verified it is added to the list of evidences
                    # BERT
                    triple_text_without_subject = triple.get_sentence(grounded_subject="<mask>",
                                                                      grounded_object=claim.object,
                                                                      extra_word=True)
                    triple_text_without_object = triple.get_sentence(grounded_subject=claim.subject,
                                                                     grounded_object="<mask>",
                                                                     extra_word=True)

                    print(triple_text_without_subject)
                    print(triple_text_without_object)
                    print(unmasker(triple_text_without_subject))
                    print(unmasker(triple_text_without_object))

                    # I get from the predicted masks only the predicted word ( contained in token_str )
                    token_guesses_subject = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                                     unmasker(triple_text_without_subject)))
                    token_guesses_object = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                                    unmasker(triple_text_without_object)))

                    if claim.subject.lower() in token_guesses_subject or claim.object.lower() in token_guesses_object:
                        print("Evidence TRUE")
                    else:
                        print("Evidence FALSE")

                    #TODO: add evidence if true to verified evidences
                # python 3.8 needed for next line
                # case in which in the triple we know one variable
                elif variable_not_known := common_member(triple.vars, claim_in_rule.vars):

                    def get_other_variable(claim_in_rule: Triple, triple: Triple, claim: Triple, variable_not_known: str):
                        """
                        claim_in_rule ex: founder(A,B)
                        triple ex: country(A,C)
                        variable_not_known: C
                        claim: founder(Tesla, Musk)

                        return: variable known from claim, so Tesla
                        """

                        # From triple I get the variable i know ( opposite of the unknown one )
                        variable_known = triple.vars[0] if triple.vars[1] == variable_not_known else triple.vars[1]

                        # I check if the variable known is the subject or object
                        if claim_in_rule.subject == variable_known:
                            return claim.subject
                        return claim.object


                    if variable_not_known == triple.subject:
                        triple_text_query = triple.get_sentence(grounded_subject="<mask>",
                                                                grounded_object=get_other_variable(claim_in_rule,
                                                                                                   triple,
                                                                                                   claim,
                                                                                                   variable_not_known),)
                    else:
                        triple_text_query = triple.get_sentence(grounded_subject=get_other_variable(claim_in_rule,
                                                                                                    triple,
                                                                                                    claim,
                                                                                                    variable_not_known),
                                                                grounded_object="<mask>")

                    token_guesses = list(map(lambda prediction: [
                                                prediction["token_str"].lower().strip(),
                                                prediction["score"]
                                            ],
                                            unmasker(triple_text_query)))

                    # Normalization of scores
                    def normalize(d: List[List[str, int]]):
                        scores = list(map(lambda x: x[1], d))
                        sum_scores = sum(scores)
                        factor = 1.0 / sum_scores
                        for tup in d:
                            tup[1] = tup[1] * factor

                        return d

                    token_guesses = normalize(token_guesses)

                    variables_not_known[variable_not_known].extend(token_guesses)
                # case in which we don't know any of the two variables
                else:
                    print("...")

        predicted_values_final = {}
        for key in variables_not_known:
            # variables_not_known[key] = sorted(variables_not_known[key], key=lambda x: x["token_str"])

            predictions = defaultdict(list)

            # loop over all predicted words with their scores and do a group by -> "America": [0.1, 0.05]
            # if a word was guessed only once it will have only one score
            for prediction in variables_not_known[key]:
                print(prediction)
                k, v = prediction
                predictions[k].append(v)

            predictions = [(k, v) for k, v in predictions.items()]

            # if at least one variable has two different possible values, max_number_of_common_prediction will be 2
            max_number_of_common_prediction = max(list(map(lambda tup: len(tup[1]), predictions)))

            # get predictions that have been predicted at least max_number_of_common_prediction times
            predictions = list(filter(lambda tup: len(tup[1]) >= max_number_of_common_prediction, predictions))

            # get total score of predictions
            predictions = list(map(lambda tup: (tup[0], sum(tup[1])), predictions))

            predicted_values_final[key] = max(predictions, key=lambda tup: tup[1])[0]

            print(predicted_values_final[key])

            # for key in predictions:
            #     predictions[key] = sorted(predictions[key], key=lambda x: (len(), prediction["score"]))



