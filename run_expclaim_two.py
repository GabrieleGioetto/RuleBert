import gspread

# google_api_credentials
from expClaim2.evidence_gatherer import find_evidences

gc = gspread.service_account('./google_api_credentials.json')

name_of_sheet = 'Ruleberto'
sh = gc.open(name_of_sheet)
sheet = sh.worksheet('Predicates')

predicates = sheet.get()

for predicate in predicates[:1]:
    rule_support = 1

    if predicate[1] == "NOT_FOUND":
        continue
    claim_text = f"{predicate[1]}({predicate[2]},{predicate[0]})"

    find_evidences(rule_support, claim_text)

