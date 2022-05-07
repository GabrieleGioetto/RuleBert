from typing import List, Dict

from src.Triple import Triple
# Install SPARQLWrapper through -> pip install sparqlwrapper
from SPARQLWrapper import SPARQLWrapper, JSON
import pickle


def query_DBpedia(query):
    sparql = SPARQLWrapper(
        "http://dbpedia.org/sparql"
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


def get_all_entities(name: str):
    query = f"""
        SELECT ?entity
        WHERE {{
            ?subject rdfs:label "{name}"@en.
            ?subject rdf:type ?entity .
        }}
    """

    result = query_DBpedia(query)

    return result


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

    entities_count = query_DBpedia(query)

    # print(entities_count)

    counts = list(map(lambda x: int(x["count"]["value"]), entities_count))
    total_number_of_entities = sum(counts)

    lower_bound = percentage_lower * total_number_of_entities
    upper_bound = percentage_upper * total_number_of_entities

    def filter_function(x):
        count = int(x["count"]["value"])
        return count < lower_bound or count > upper_bound

    entities_to_remove = list(filter(lambda x: filter_function(x), entities_count))

    # I remove the count property
    entities_to_remove = list(map(lambda x: {"entity": x["entity"]}, entities_to_remove))

    with open("data/entities_to_remove.pkl", "wb") as f:
        pickle.dump(entities_to_remove, f)

    print("SAVED FILE")


def filter_entities(_entities: List[Dict]):
    with open("data/entities_to_remove.pkl", "rb") as f:
        entities_to_remove = pickle.load(f)

    _entities = list(filter(lambda e: e not in entities_to_remove, _entities))

    return _entities


def add_context(triple: Triple):
    triple_subject: str = triple.subject
    triple_object: str = triple.subject
    sentence_nl = triple.get_sentence(grounded_subject=triple_subject, grounded_object=triple_object, extra_word=False)


# print(*get_all_entities("Cristiano Ronaldo"), sep='\n')
entities = get_all_entities("Cristiano Ronaldo")
# save_entities_to_remove()
entities = filter_entities(entities)

print(*entities, sep='\n')
