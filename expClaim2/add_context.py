# Install SPARQLWrapper through -> pip install sparqlwrapper
import pickle
import requests
from collections import Counter
from urllib.parse import quote
import wordninja

from expClaim2.util import query_dbpedia, query_wikidata, get_all_entities, filter_entities, get_entity_count


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
    # if the entity is from wikidata, I get the label from wikidata
    if entity.split("//")[1].startswith("www.wikidata.org"):
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
        PREFIX wd: <http://www.wikidata.org/entity/> 
        select *
        where {{
                wd:{entity.split("/")[-1]} rdfs:label ?label .
          FILTER (langMatches( lang(?label), "EN" ) )
              }}
        LIMIT 1
        """

        result = query_wikidata(query)

        if result is not None:
            return result
    else:
        # if the entity is from dbpedia, I get the label from dbpedia
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


def get_salient_from_entity(entities):
    i = 0
    salient_type = None
    while salient_type is None and i < len(entities):
        salient_type = get_label_name_from_entity(entities[i])
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
        salient_type = entities_count[0][0]

        salient_type = "".join(list(filter(lambda x: x.isalpha(), salient_type.split("/")[-1].lower())))

        salient_type = " ".join(wordninja.split(salient_type))

    return salient_type


def get_salient_type(entity_name: str):
    entities = get_all_entities(entity_name)

    # Not found label on dbPedia
    if len(entities) == 0:
        return None

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

            salient_type = None
            i = 0
            while salient_type is None and i < len(most_commons_types_between_similar):
                type_of_subject = most_commons_types_between_similar[i]
                salient_type = get_label_name_from_entity(type_of_subject)

                i += 1

            # If label not present in the entity in dbPedia
            if salient_type is None:
                salient_type = "".join(list(filter(lambda x: x.isalpha(), type_of_subject.split("/")[-1].lower())))

                salient_type = " ".join(wordninja.split(salient_type))
        else:
            salient_type = get_salient_from_entity(entities)

    return salient_type


def add_context(sentence: str, entity: str):
    entity_type = get_salient_type(entity)

    if entity_type is None:
        return sentence

    _to_return = f"{entity} is a {entity_type}. {sentence}"
    return _to_return


def main():
    print(get_salient_type("Cristiano Ronaldo"))


if __name__ == '__main__':
    main()
