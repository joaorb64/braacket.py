from bs4 import BeautifulSoup
import requests
import re 
from difflib import SequenceMatcher

class Braacket:
    
    def __init__(self, league):
        # https://braacket.com/league/{league}
        # https://braacket.com/league/{league}/player?rows=200
        # ie: 'NCMelee'
        self.league = league
        #self.update_player_cache()
        return

    def update_player_cache(self):
        # pretty straight forward. the leagues are their name
        # in the url, however as you'll see later on, players
        # have a unique id assigned to them that we have to 
        # extract with BeautifulSoup

        # player cache is laid out as such:
        # {
        #   'tag1': 'uuid',
        #   'tag2': 'uuid',
        #   'tag3': 'uuid',
        #   ...
        # }
        r = requests.get(
            'https://braacket.com/league/'
            f'{self.league}/player?rows=200', verify=False)
            # the upperbound is 200
        soup = BeautifulSoup(r.text, 'html.parser')
        # <table class='table table-hover'> -v
        # <tbody> -> <tr> -> <td> -> <a> {player}
        players = soup.select("table.table.table-hover a")
        self.player_cache = {}
        # /league/{league}/player/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        url_extract = re.compile(r'.*\/([^\/]*)')
        for player in players:
            # BeautifulSoup returns exactly one empty
            # player, not sure why...
            if not player.string:
                continue
            # match // extract, potential for a mtg fuse spell
            uuid = url_extract.match(player['href']).group(1)
            self.player_cache[player.string] = uuid
    
    def get_ranking(self):
        # returns player ranking with basic data available at the ranking page

        # ranking data is laid out as such:
        # {
        #   'uuid': {
        #       'name': "player tag (string)",
        #       'rank': "player rank (int)",
        #       'score': "player score (int)",
        #       'mains': [
        #           {
        #               'icon': "braacket character icon url (string)",
        #               'name': "character name (string)"
        #           },
        #           ...
        #       ]
        #   },
        #   ...
        # }
        r = requests.get(
            'https://braacket.com/league/'
            f'{self.league}/ranking?rows=200&embed=1', verify=False) # the upperbound is 200
        soup = BeautifulSoup(r.text, 'html.parser')

        table = soup.findAll('table')[1] # first table is ranking system, second has the player list
        tbody = table.find('tbody') # skip the table's header
        lines = tbody.select("tr") # get each of the table's lines
        url_extract = re.compile(r'.*\/([^\/][^?]*)') # /league/{league}/player/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

        pranking = {}

        for line in lines:
            children = line.findChildren(recursive=False)

            # [ [rank][0]- [icon][1] - [player name, mains][2] - [social media][3] - [?][4] - [score][5] ]

            # uuid
            uuid = url_extract.match(children[2].find('a')['href']).group(1)
            pranking[uuid] = {}

            # rank
            rank = children[0].string.strip()
            pranking[uuid]["rank"] = rank

            # name
            pranking[uuid]["name"] = children[2].find('a').string

            # mains
            pranking[uuid]["mains"] = []
            mains = children[2].findAll('img')

            for main in mains:
                character = {}
                character["name"] = main["title"]
                character["icon"] = main["src"]
                pranking[uuid]["mains"].append(character)

            # twitter
            links = children[3].select('a')

            for link in links:
                if link.has_attr('href'):
                    if "twitter.com" in link['href']:
                        pranking[uuid]["twitter"] = link['href']
            
            # score
            score = children[5].string.strip()
            pranking[uuid]["score"] = score
        return pranking

    def get_league_name(self):
        # returns the league's name
        r = requests.get(
            'https://braacket.com/league/'f'{self.league}', verify=False)
        soup = BeautifulSoup(r.text, 'html.parser')

        titleContainer = soup.findAll('div', {"class": "content_header-body"})[0]
        title = titleContainer.find('h1')

        return title.find('a').string

    def player_search(self, tag):
        tag = tag.strip()
        probability_list = []
        # use SequenceMatcher to run the match ratio of each
        # tag in the cache against the searched tag. sort them
        # from most likely to least likely. all tags that contain
        # the substring of -tag- get a boost in relevance. 
        for key in list(self.player_cache.keys()):
            probability = SequenceMatcher(
                None, tag.lower(), key.lower()
                ).ratio()
            p_dict = {}
            p_dict['tag'] = key
            p_dict['uuid'] = self.player_cache[key]
            p_dict['probability'] = probability
            probability_list.append(p_dict)
        # for each tag in the probability_list, if the search
        # term is a substring, then boost it's relevance
        # significantly. 
        for name in probability_list:
            if tag.lower() in name['tag'].lower():
                name['probability'] += 1.0
        # once the probability list is populated,
        # sort it by probability, most likely to least
        probability_list = sorted(
            probability_list, 
            key=lambda prob: 2-prob['probability'])
        # [{
        #   'tag': matched tag
        #   'uuid': uuid 
        #   'probability': probability (float)
        # }, {...}, ... ]
        # top 8 results

        return probability_list[:8]

    def player_stats(self, uuid):
        r = requests.get(
            'https://braacket.com/league/'
            f'{self.league}/player/{uuid}', verify=False)
        soup = BeautifulSoup(r.text, 'html.parser')
        player_stats = {} # gonna fill this w/ a lot of stuff
        # :: TAG ::      
        # tag can be found in: 
        # <tr> -> <td> -> <h4 class='ellipsis'>
        tag = soup.select("tr td h4.ellipsis")[0].get_text().strip()
        player_stats['tag'] = tag
        # :: RANKING :: 
        try:
            ranking_info = soup.select(
                'section div.row div.col-lg-6 '
                'div.panel.panel-default.my-box-shadow '
                'div.panel-body '
                'div.my-dashboard-values-main')[0].stripped_strings # generator
            ranking_info = [text for text in ranking_info] # array !
            rank_int = int(ranking_info[0]) # rank
            out_of_extract = re.compile(r'\/ ([0-9]+)$')
            out_of = out_of_extract.match(ranking_info[2]).group(1) # '/ XXXX'
            out_of_int = int(out_of)
            ranking = {
                'rank': rank_int,
                'rank_suffix': ranking_info[1], 
                'out_of': out_of_int 
            }
        except IndexError: #rank -1 means unranked
            ranking = {
                'rank': -1,
                'rank_suffix': 'st', 
                'out_of': -1
            }
        # get info from the rest of the sub-panels
        # these can be things like, the date range of
        # the player, the ranking type, their raw score,
        # the activity requirements, and whether or not
        # the player meets said requirement. 
        sub_panels = soup.select(
            'section div.row div.col-lg-6 '
            'div.panel.panel-default.my-box-shadow '
            'div.panel-body '
            'div.my-dashboard-values-sub')
        sub_panels_stripped = {}
        for panel in sub_panels:
            panel_array = [text for text in panel.stripped_strings]
            # take the 1st item, lower its case, and make it the key.
            # take the rest of the items in the array, and join them with
            # a space and make it the value.
            sub_panels_stripped[panel_array[0].lower()] = ' '.join(panel_array[1:])
            ranking = {**ranking, **sub_panels_stripped} # merge into ranking dict
        exclusion_check = soup.select(
            'section div.row div.col-lg-6 '
            'div.panel.panel-default.my-box-shadow '
            'div.panel-body '
            'div.my-dashboard-values-sub div i.fa-exclamation-triangle') # inactive
        ranking['inactive'] = (len(exclusion_check) > 0)
        if 'score' in ranking: # one off, maybe do these in bulk later
            ranking['score'] = int(ranking['score'])
        # example: 
        # {
        #   'rank': 33, (int)
        #   'rank_suffix': 'rd' (str)
        #   'out_of': 2333, (int)
        #   'score': 1234, (int)
        #   'type': 'TrueSkill™', (str)
        #   'date': '04 December 2017 - 31 December 2018', (str)
        #   'activity requirement': 'Requires 4 tournaments played within last 4 months' (str)
        #   'inactive': True
        # }
        player_stats['ranking'] = ranking
        # :: PERFORMANCE STATISTICS ::
        performance = {}
        try:
            win_rate = soup.select(
                'div.panel.panel-default.my-box-shadow.my-panel-collapsed '
                'div.panel-body div.alert div.my-dashboard-values-main')[0].stripped_strings
            win_rate = [text for text in win_rate] # generator to array
            # number is at the beginning of the scrape
            win_rate_extract = re.compile(r'([0-9]+)') 
            # get the number, make it a float
            win_rate = float(win_rate_extract.match(win_rate[0]).group(1)) 
            performance['win_rate'] = win_rate/100.0
            # various stats from the page
            # these include: wins, draws, losses, +, -, +/-, top 1,
            #                top 3, top 8, top 16, top 32, worst, and potentially
            #                more depending on what braacket adds
            stats_table_prefilter = soup.select(
                'div.panel.panel-default.my-box-shadow.my-panel-collapsed '
                'div.panel-body table.table tbody tr')
            stats_table = []
            for row in stats_table_prefilter:
                wdl_item = [text for text in row.stripped_strings]
                stats_table.append(wdl_item)
            # lots of stuff uses the css rules, so we're narrowing it to 
            # just the items that have a stat and a value assigned to that stat
            stats_table = [item for item in stats_table if len(item) == 2]
            for stat in stats_table:
                performance[stat[0].lower()] = int(stat[1])
        except IndexError:
            pass

        player_stats['performance'] = performance
        return player_stats

    def head_to_head(self, uuid1, uuid2):
        h2h_return = {}
        # note! dates are 1 indexed for all fields

        # :::::::: STATS ::::::::
        # use the uuids to open the compare page
        h2h_url = ('https://braacket.com/league/' 
            f'{self.league}/player/{uuid1}'
            f'?player_hth={uuid2}')
        r = requests.get(h2h_url, verify=False)
        soup = BeautifulSoup(r.text, 'html.parser')
        # use the text 'Head to Head' to search for the relevant info
        h2h_siblings = soup.find(string=re.compile("Head to Head")).parent.next_siblings
        h2h_stats_tag = None
        # the info we need is somewhere after the area that we find 'Head to Head'.
        # search for it, make note of the tag, and then break
        for h2h_sibling in h2h_siblings:
            # it's designated by div.panel-body
            if 'panel-body' in str(h2h_sibling):
                h2h_stats_tag = h2h_sibling
                break
        # create a generator of stripped strings (generators themselves)
        # for each generator found in the select search
        gen = (x.stripped_strings for x in h2h_stats_tag.select('table tbody tr td'))
        # h2h_values_list is a list of all the values from the generators run together
        h2h_values_list = []
        # h2h_values will hold the key-value pairs of relevant info
        h2h_values = {}
        # for each html tag (already stripped-string versions)
        for tag in gen:
            # for each piece of text in each stripped-string generator
            for text in tag:
                # if it's castable to an int, add it to the list.
                # otherwise, add the text to the list.
                try: 
                    h2h_values_list.append(int(text))
                except ValueError:
                    h2h_values_list.append(text.lower())
        # make a list of all the indices of the ints. then for each one of these
        # indices, make the element before it the key to said int value. 
        h2h_value_indices = [i for i, x in enumerate(h2h_values_list) if type(x) == int]
        for i in h2h_value_indices:
            h2h_values[h2h_values_list[i-1]] = h2h_values_list[i]
        h2h_return['stats'] = h2h_values # add to return object

        # :::::::: RECENT MATCH ::::::::
        soup = BeautifulSoup(r.text, 'html.parser')
        # use the text 'Matches history' to search for the relevant info
        matches_siblings = soup.find(string=re.compile("Matches history")).parent.next_siblings
        matches_stats_tag = None
        for matches_sibling in matches_siblings:
            if 'panel-body' in str(matches_sibling):
                matches_stats_tag = matches_sibling
                break
        gen = (x.stripped_strings for x in matches_stats_tag.select('table tbody tr td'))
        matches_values_list = []
        for tag in gen:
            for text in tag:
                matches_values_list.append(text)
        # slightly different logic than above, just get the most recent match.
        # info is found at fixed offsets. if they haven't played, return False for
        # 'recent'
        match_values = {}
        try:
            match_values['name']  = matches_values_list[0]
            match_values['score'] = matches_values_list[4]
            match_values['date']  = matches_values_list[5]
            h2h_return['recent']  = match_values
        except:
            h2h_return['recent']  = False

        # [:: example ::]
        # {
        #  'stats': {
        #   'win': 0,
        #   'draw': 0,
        #   'lose': 5,
        #   'win rate': 0,
        #   '+': 3,
        #   '-': 13,
        #   '+/-': -10
        #  },
        #  'recent': {
        #   'name': 'Geeks Weekly 57',
        #   'date': '2018-08-02'
        #   'score': '1-2'
        #  }
        # }
        return h2h_return
