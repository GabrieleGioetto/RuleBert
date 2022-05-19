from typing import List

from src.Triple import Triple
# Install SPARQLWrapper through -> pip install sparqlwrapper
from SPARQLWrapper import SPARQLWrapper, JSON
import pickle
import requests
from collections import Counter
from urllib.parse import quote


def query_dbpedia(query):
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


def get_all_types_of_subject(subject: str):
    query = f"""SELECT DISTINCT ?object 
    WHERE
    {{
        {{
            ?subject rdf:type ?object 
            FILTER (?subject = <{subject}>)
        }}
        UNION
        {{
            ?subject dbo:type ?object
            FILTER (?subject = <{subject}>)

        }}
    }}
    LIMIT 20
    """

    result = query_dbpedia(query)

    return result


def get_label_name_from_entity(entity: str):
    query = f"""SELECT DISTINCT ?object 
    WHERE
    {{
        ?entity rdfs:label ?object 
        FILTER (?entity = <{entity}>)
        FILTER(langMatches(lang(?object),"en"))
    }}
    LIMIT 1
    """

    result = query_dbpedia(query)

    if len(result) > 0:
        return result[0]["object"]["value"]

    return None


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


def add_context(sentence: str, entity: str):
    entity_type = get_salient_type(entity)

    _to_return = f"{entity} is a {entity_type}. {sentence}"
    return _to_return


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


def get_salient_from_entity(entities):
    i = 0
    salient_type = None
    while salient_type is None and i < len(entities):
        salient_type = get_label_name_from_entity(entities[i])
        # print(f"entities[i]: {entities[i]}")
        # print(f"salient_type: {salient_type}")
        i += 1

    if salient_type is None:
        # TODO: order by most viewed entity and get split string from link ( ex: .../yago/SoccerPlayer1223 -> soccer player )
        entities_count = []
        for entity in entities:
            entities_count.append((entity, get_entity_count(entity)))

        # print(entities_count)
        # reverse order
        entities_count = sorted(entities_count, key=lambda tup: -tup[1])

        # I pick the most frequent
        salient_type = entities_count[0]
    return salient_type


def get_salient_type(entity_name: str):
    entities = get_all_entities(entity_name)
    # save_entities_to_remove()
    entities = filter_entities(entities)

    # print(*entities, sep='\n')

    kg2vec_dbpedia_api = "http://www.kgvec2go.org/rest/closest-concepts/dbpedia"
    number_of_responses = 20

    rest_query = f"{kg2vec_dbpedia_api}/{number_of_responses}/{quote(entity_name)}"

    response = requests.get(rest_query)

    all_types = Counter()

    if len(response.json()) <= 0:
        return get_salient_from_entity(entities)

    with open("data_generation/data/entities_to_remove.pkl", "rb") as f:
        entities_to_remove = pickle.load(f)

        for similar_entity in response.json()["result"]:

            types = get_all_types_of_subject(subject=similar_entity["concept"])
            for _type in types:
                type_value = _type["object"]["value"]
                if type_value not in entities_to_remove:
                    all_types[type_value] += 1

        n_most_common = 10

        most_commons_types_between_similar = all_types.most_common(n=n_most_common)

        most_commons_types_between_similar = list(map(lambda tup: tup[0], most_commons_types_between_similar))

        most_commons_types_between_similar = filter_entities(most_commons_types_between_similar)

        most_commons_types_between_similar = list(filter(lambda x: x in entities, most_commons_types_between_similar))

        # I get the most common entity type between similar (Ex. Cristiano Ronaldo -> SoccerPlayer)
        if len(most_commons_types_between_similar) > 0:
            type_of_subject = most_commons_types_between_similar[0]
            # print(f"type_of_subject: {type_of_subject}")

            salient_type = get_label_name_from_entity(type_of_subject)

            # If label not present in the entity in dbPedia
            if salient_type is None:
                salient_type = "".join(list(filter(lambda x: x.isalpha(), type_of_subject.split("/")[-1].lower())))
        else:
            salient_type = get_salient_from_entity(entities)

    return salient_type


def main():
    print(get_salient_type("Cristiano Ronaldo"))


if __name__ == '__main__':
    main()

