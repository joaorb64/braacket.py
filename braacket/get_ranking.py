import braacket
import pprint
import json

bracket = braacket.Braacket('liga_ultra_arcade_s1')

ranking = bracket.get_ranking()

pp = pprint.PrettyPrinter()

pp.pprint(ranking)

with open('ranking.json', 'w') as outfile:
  json.dump(ranking, outfile)