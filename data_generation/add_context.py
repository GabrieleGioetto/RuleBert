from src.Triple import Triple
# Install SPARQLWrapper through -> pip install sparqlwrapper
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper(
    "http://dbpedia.org/sparql"
)
sparql.setReturnFormat(JSON)

# gets the first 3 geological ages
# from a Geological Timescale database,
# via a SPARQL endpoint

query = """
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    prefix dbo: <http://dbpedia.org/ontology/> 
    prefix wdt: <http://www.wikidata.org/prop/direct/> 
    prefix wd: <http://www.wikidata.org/entity/> 
    prefix dbr: <http://dbpedia.org/resource/>

    SELECT DISTINCT ?subject ?relation ?object 
    WHERE { ?subject rdf:type <http://dbpedia.org/ontology/Person>.
    ?object rdf:type <http://dbpedia.org/ontology/Place>.
    ?subject ?relation ?object. 
    FILTER (?subject = <http://dbpedia.org/resource/Barack_Obama>)
    FILTER(?object = <http://dbpedia.org/resource/Honolulu>)
    } 
    limit 1000
    """

query = """
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    prefix dbo: <http://dbpedia.org/ontology/> 
    prefix wdt: <http://www.wikidata.org/prop/direct/> 
    prefix wd: <http://www.wikidata.org/entity/> 
    prefix dbr: <http://dbpedia.org/resource/>

    SELECT DISTINCT ?subject rdf:type ?object 
    WHERE
    {
        FILTER (?subject = <http://dbpedia.org/resource/Cristiano_Ronaldo>)
    }
    LIMIT 10
"""

sparql.setQuery(query)

try:
    ret = sparql.queryAndConvert()

    for r in ret["results"]["bindings"]:
        print(r)
except Exception as e:
    print(e)


def add_context(triple: Triple):

    triple_subject: str = triple.subject
    triple_object: str = triple.subject
    sentence_nl = triple.get_sentence(grounded_subject=triple_subject, grounded_object=triple_object, extra_word=False)


