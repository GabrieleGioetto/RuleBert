import pickle
from typing import List

import gspread
from SPARQLWrapper import SPARQLWrapper, JSON

from data_generation.src import Triple


def common_member(triple: List[str], claim: List[str]):
    triple_set = set(triple)
    claim_set = set(claim)
    if len(triple_set.intersection(claim_set)) > 0:
        diff = triple_set.difference(claim_set)
        if diff:
            return list(diff)[0]
    return False


# Normalization of scores
def normalize(d):
    scores = list(map(lambda x: x[1], d))
    sum_scores = sum(scores)
    factor = 1.0 / sum_scores
    for tup in d:
        tup[1] = tup[1] * factor

    return d


def get_other_variable(claim_in_rule: Triple, triple: Triple, claim: Triple,
                       variable_not_known: str):
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


def query_dbpedia(query):
    sparql = SPARQLWrapper(
        "http://dbpedia.org/sparql",
    )
    sparql.setReturnFormat(JSON)

    query = """
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix dbo: <http://dbpedia.org/ontology/>
        prefix wdt: <http://www.wikidata.org/prop/direct/>
        prefix wd: <http://www.wikidata.org/entity/>
        prefix dbr: <http://dbpedia.org/resource/>
    """ + query

    sparql.setQuery(query)

    ret = sparql.queryAndConvert()

    return ret["results"]["bindings"]


def query_wikidata(query, column="label"):
    sparql = SPARQLWrapper(
        "https://query.wikidata.org/sparql",
        agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11"
    )
    sparql.setReturnFormat(JSON)

    sparql.setQuery(query)

    ret = sparql.queryAndConvert()

    if "results" in ret and len(ret["results"]["bindings"]) > 0:
        return ret["results"]["bindings"][0][column]["value"]


def get_all_entities(name: str):
    query = f"""
        SELECT ?entity
        WHERE {{
            {{
                ?subject rdfs:label "{name}"@en.
                ?subject rdf:type ?entity
            }}
            UNION
            {{
                ?subject rdfs:label "{name}".
                ?subject dbo:type ?entity
            }}
        }}
    """

    result = query_dbpedia(query)

    entities = list(map(lambda x: x["entity"]["value"], result))

    return entities


def save_entities_to_remove(percentage_lower=0.000005, percentage_upper=0.005):
    query = """
    SELECT ?entity, (COUNT(*) AS ?count)
           WHERE {
                ?subject rdf:type ?entity .
            }
    GROUP BY ?entity
    ORDER BY DESC(?count)
    LIMIT 40000
    """

    entities_count = query_dbpedia(query)

    # print(entities_count)

    counts = list(map(lambda x: int(x["count"]["value"]), entities_count))
    total_number_of_entities = sum(counts)

    lower_bound = percentage_lower * total_number_of_entities
    upper_bound = percentage_upper * total_number_of_entities

    def filter_function(x):
        count = int(x["count"]["value"])
        return count < lower_bound or count > upper_bound

    entities_to_remove = list(filter(lambda x: filter_function(x), entities_count))

    # I remove the count property and keep only the url
    entities_to_remove = list(map(lambda x: x["entity"]["value"], entities_to_remove))

    with open("data_generation/data/entities_to_remove.pkl", "wb") as f:
        pickle.dump(entities_to_remove, f)

    print("SAVED FILE")


def filter_entities(_entities: List[str]):
    with open("data_generation/data/entities_to_remove.pkl", "rb") as f:
        entities_to_remove = pickle.load(f)

    _entities = list(filter(lambda e: e not in entities_to_remove, _entities))

    return _entities


def get_entity_count(entity: str):
    query = f"""SELECT (COUNT(*) AS ?count)
           WHERE {{
                ?subject rdf:type <{entity}>.
            }}
    """

    result = query_dbpedia(query)

    if len(result) > 0:
        return int(result[0]["count"]["value"])

    return None


def save_context_to_google_sheet(context_list, claim):
    """

    Args:
        context_list:  context list ( facts + rule )
        claim: our initial hypothesis

    Returns:

    """

    # Google sheet
    gc = gspread.service_account("google_api_credentials.json")

    name_of_sheet = 'Ruleberto'
    sh = gc.open(name_of_sheet)
    sheet = sh.worksheet('Rules')

    claim_text = claim.get_sentence(claim.subject, claim.object, extra_word=True)

    for _context in context_list:
        sheet.append_row([claim_text, _context])