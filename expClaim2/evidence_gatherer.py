from expClaim2.add_context import add_context
from expClaim2.util import common_member, normalize, get_other_variable, save_context_to_google_sheet
from data_generation.src import Rule
from data_generation.src import Triple

from transformers import pipeline
import argparse
import pickle

from collections import defaultdict

my_parser = argparse.ArgumentParser(description='Get evidence with BERT')

my_parser.add_argument('--support',
                       type=float,
                       help='Support')

my_parser.add_argument('--claim',
                       type=str,
                       help='Claim')

args = my_parser.parse_args()


def find_evidences(rule_support, claim_text):
    claim = Triple(claim_text)
    print(claim.get_sentence(claim.subject, claim.object, extra_word=True))

    with open('data_generation/data/rule2text.pkl', 'rb') as f:
        rule2text = pickle.load(f)

    # rule_in_english = rule2text[rule_text]

    # I pick the top 20 prediction from BERT
    k = 20
    unmasker = pipeline('fill-mask', model='roberta-base', tokenizer="roberta-base", top_k=k)

    # List with all contexts generated
    context_list = []

    # Loop over all rules saved locally
    for rule_key in rule2text:

        facts = ""

        # check if in current rule there is the relation we are trying to verify the trueness
        if claim.relation not in rule_key:
            continue

        rule = Rule(rule=rule_key)
        rule.set_rule_support(rule_support)
        rule.add_rule_info(rule_key)

        # to avoid neg relations ( I look for founder, I find negfounder)
        if claim.relation not in rule.relations:
            continue

        # I keep only the rules that have the relation we are trying to verify in the head
        if claim.relation != rule.head.relation:
            continue

        # Simple case: I just keep rule with only 3 vars and no negation
        if rule.num_vars > 3 or "neg" in str(rule):
            continue

        rule_description = rule.description

        print(f"{'-' * 20} Rule {'-' * 20}")
        print(rule)
        print("--- End Rule ---")

        facts = get_facts(claim, facts, rule, unmasker)

        context = facts + " " + rule_description

        context_list.append(context)

    save_context_to_google_sheet(context_list, claim)


def get_facts(claim, facts, rule, unmasker):
    # I assume claim relation is present only once in the rule
    claim_in_rule = list(filter(lambda t: t.relation == claim.relation, rule.triples))[0]

    variables_not_known = defaultdict(list)

    # I iterate over all triplets in the rule which are different then the one in the claim
    # If they have a subset of the variables in the claim
    # if triple.relation != claim.relation and set(triple.subject_list).issubset(set(claim_in_rule.subject_list)):
    for triple in rule.triples:

        if triple.relation != claim.relation:

            # case in which in the triple we know both variables
            if sorted(triple.vars) == sorted(claim_in_rule.vars):
                # add that if the triple is verified it is added to the list of evidences
                # BERT
                facts += get_evidence_both_variables_known(claim, triple, unmasker) + " "
            # python 3.8 needed for next line
            # case in which in the triple we know one variable
            elif variable_not_known := common_member(triple.vars, claim_in_rule.vars):
                # Predict the variables that are not known

                known_variable = get_other_variable(claim_in_rule, triple, claim, variable_not_known)

                if variable_not_known == triple.subject:
                    triple_text_query = triple.get_sentence(grounded_subject="<mask>",
                                                            grounded_object=known_variable)
                else:
                    triple_text_query = triple.get_sentence(grounded_subject=known_variable,
                                                            grounded_object="<mask>")

                # Add the context ( See add_context.py )
                triple_text_query = add_context(triple_text_query, known_variable)

                token_guesses = list(map(lambda pred: [
                    pred["token_str"].lower().strip(),
                    pred["score"]
                ],
                                         unmasker(triple_text_query)))

                token_guesses = normalize(token_guesses)

                # Add prediction of the variable value to a dictionary
                variables_not_known[variable_not_known].extend(token_guesses)
            # case in which we don't know any of the two variables
            else:
                print("...")

    for key in variables_not_known:
        facts += get_evidence_one_variable_known(claim, claim_in_rule, key, rule, variables_not_known)

    return facts


def get_evidence_one_variable_known(claim, claim_in_rule, key, rule, variables_not_known):
    """
    Args:
        claim: claim triple
        claim_in_rule: claim triple inside the rule
        key: variable not known in the claim
        rule: complete rule
        variables_not_known: dict with all variables not known

    Returns: facts generated as string

    """

    predictions = defaultdict(list)

    # loop over all predicted words with their scores and do a group by -> "America": [0.1, 0.05]
    # if a word was guessed only once it will have only one score
    for prediction in variables_not_known[key]:
        k, v = prediction
        predictions[k].append(v)

    predictions = [(k, v) for k, v in predictions.items()]

    # if at least one variable has two different possible values, max_number_of_common_prediction will be 2
    max_number_of_common_prediction = max(list(map(lambda tup: len(tup[1]), predictions)))

    # get predictions that have been predicted at least max_number_of_common_prediction times
    predictions = list(filter(lambda tup: len(tup[1]) >= max_number_of_common_prediction, predictions))

    # get total score of predictions
    predictions = list(map(lambda tup: (tup[0], sum(tup[1])), predictions))

    prediction_max = max(predictions, key=lambda tup: tup[1])[0]
    confidence = max(predictions, key=lambda tup: tup[1])[1]

    print(f"Prediction for key {key} with confidence {confidence}:  {prediction_max}")
    print("\n" * 6)

    _facts = get_facts_from_variable_and_rule(key, prediction_max, rule, claim, claim_in_rule)
    return _facts


def get_evidence_both_variables_known(claim, triple, unmasker):
    """

    Args:
        claim: claim triple
        triple: a triple inside the rule
        unmasker: bert unmasker

    Returns: facts generated as string

    """
    _facts = ""

    triple_text_without_subject = triple.get_sentence(grounded_subject="<mask>",
                                                      grounded_object=claim.object,
                                                      extra_word=True)
    triple_text_without_object = triple.get_sentence(grounded_subject=claim.subject,
                                                     grounded_object="<mask>",
                                                     extra_word=True)
    # I get from the predicted masks only the predicted word ( contained in token_str )
    token_guesses_subject = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                     unmasker(triple_text_without_subject)))
    token_guesses_object = list(map(lambda prediction: prediction["token_str"].lower().strip(),
                                    unmasker(triple_text_without_object)))
    if claim.subject.lower() in token_guesses_subject or claim.object.lower() in token_guesses_object:
        print("Evidence TRUE")
        _facts += triple.get_sentence(grounded_subject=claim.object, grounded_object=claim.subject)
    else:
        print("Evidence FALSE")

    return _facts


def get_facts_from_variable_and_rule(variable, prediction, rule, claim, claim_in_rule):
    """

    Args:
        variable: variable to get facts from
        prediction:
        rule: rule to get facts from
        claim:
        claim_in_rule: claim to get facts from

    Returns: facts from variable and rule

    """

    _facts = []

    variables_from_claim = [claim.subject, claim.object]
    variables_known = dict(map(lambda x: (x[0], x[1]), zip(claim_in_rule.vars, variables_from_claim)))

    for triple in rule.triples:
        if variable in triple.vars:
            if variable == triple.subject:
                _facts.append(triple.get_sentence(grounded_subject=prediction,
                                                  grounded_object=variables_known[triple.object]))
            elif variable == triple.object:
                _facts.append(triple.get_sentence(grounded_subject=variables_known[triple.subject],
                                                  grounded_object=prediction))

    return " ".join(_facts)


def main():
    rule_support = args.support  # String of the rule
    claim_text = args.claim

    find_evidences(rule_support, claim_text)


if __name__ == '__main__':
    main()
