import re
from fuzzywuzzy import process
from math import pow, sqrt
import sys

class Location:
    '''
    A geolocated Location
    '''
    new_lat = 0
    new_long = 0
    location = ''
    original_qds = ''
    original_lat = 0
    original_long = 0
    province = ''
    directions = {'direction': '', 'distance': '', 'measurement': ''}
    farm_number = 0
    notes = ''
    farms = []
    gazetteer = []
    google_geolocator = None

    def __init__(self, province='', qds='', lat='', long='', location='', farms=[], gazetteer=[], google_geolocator=None):
        self.province = province
        self.original_qds = qds
        self.original_lat = float(lat)
        self.original_long = float(long)
        self.location = location
        self.farms = farms
        self.gazetteer = gazetteer
        self.google_geolocator = google_geolocator

        print(location)

        # Clean the location string
        self._clean_location()

        # If the loc is x km from something etc then try and get the location and clean the location string further
        self._get_directions()

        print(location)

        # Does this location string contain something?
        if self.location.strip() is '':
            # TODO if loc is blank then it needs to get the center from Fhatani's script (input qds) which he still has to write
            return

        # Is this location a park?
        if self._is_park():
            # TODO Fhatani will add a list of all parks and iterate over them
            pass

        # Otherwise, is this location a farm?
        if self._is_farm():
            self._surveyor_general_farm_processing()
            # TODO add les' database farm processing

        # Otherwise geolocate using google maps and les's database
        self._geolocate_google()
        self._geolocate_gazetteer()

    def _geolocate_gazetteer(self):
        pass

    def _geolocate_google(self):
        try:
            results = self.google_geolocator.geocode(query=self.location + ', ' + self.province, region='za')

            # Has it actually managed to find coords beyond province level? and are we in the right country?
            country = ''
            for addresscomponent in results.raw['address_components']:
                if addresscomponent['types'] == ['country', 'political']:
                    country = addresscomponent['short_name']

            if str(results) != self.province + ", South Africa" and country == 'ZA':
                lat = results.raw['geometry']['location']['lat']
                lng = results.raw['geometry']['location']['lng']
                # We are finding the difference in x and y between a point (i.e., x degrees)
                self.notes = "Google maps API geolocates this as: " + results.raw['geometry']['location_type'] + " - distance from original qds = " + pow(float(lat) - self.original_lat, 2) + pow(float(lng) - self.original_long, 2)
                # a ^ 2 + b ^ 2 = c ^ 2 !!!
            # else:
                # Try it without bounding, maybe clean the loc a bit more too?
                # results = geolocate.geocode(query=loc + ', ' + province, region='za')
        except AttributeError as e:
            print("Google maps could not find :" + self.location + ' gives error : ' + str(sys.exc_info()))
        except:
            print("ANOTHER ERROR occurred when looking up in google " + str(sys.exc_info()))
            # At this stage perhaps we should run it through bing or another map.

    def _clean_location(self):
        '''
        Removes superfluous strings which just confuse stuff
        '''
        # National parks and nature reserves are often written in strange ways, let's correct them
        self.location = re.sub(r'Nat\.?\s+[pP]ark\.?', 'National Park', self.location)
        self.location = re.sub(r'Nat\.?\s+[rR]es\.?', 'Nature Reserve', self.location)
        self.location = re.sub(r'\s+N\.?\s?R\.?\s+', 'Nature Reserve', self.location)
        self.location = re.sub(r'\s+N(at)?\.?\s?P(ark)?\.?\s+', 'National Park', self.location)

        # A lot of them have the string "snake collected from x", remove that
        self.location = re.sub(r'^\w+?\s*[cC]ollected\s+[fF]rom\s*', '', self.location)

        # I am not sure what this means but often things have K[letter]\d\d+ and that messes stuff up
        self.location = re.sub(r'^\s+\d{3,4}K[RSTUV]\s+', '', self.location)

        # Some stuff in phrases is just useless and all that comes after it, so remove
        phrases = ['along the top of', 'at the bottom of', 'nearby', 'next to']
        for phrase in phrases:
            self.location = re.sub(r'\s*' + re.escape(phrase) + r'.*', ', ', self.location)

        # A lot of things have been put in the proper address then a semi colon and random comments, so get rid of these
        self.location = re.sub(r';.+$', '', self.location)

    def _is_farm(self):
        temp = self.location

        # Remove "in the / on the" for farms
        self.location = re.sub(r'[\w\s]+?\s*[OoIi]n\s+(the\s+)?[Ff]arm\s*', 'Farm', self.location)

        # Farm x, blah blah blah (we don't need the blah blah blah bit, so remove it and strip out the "Farm"
        self.location = re.sub(r'^\s*Farm\s*(.+?),.+', "\g<1>", self.location)

        # If this string contains three digits it's very likely to be a farm number
        # Alternate regex ^(([A-Za-z\-]+\s*?){1,4}),?\s?[\(\[\{]?(\d{3})[^\.].*$
        results = re.search('\s*[\[\{\(]?\s*(\d\d\d)\s*[\]\}\)]?\s*', self.location, re.IGNORECASE)
        if results and results.group(1):
            self.location = self.location.replace(results.group(0), '')
            self.farm_number = results.group(1)

        # If anything has changed in the location string after this then it is a farm
        return temp == self.location

    def _surveyor_general_farm_processing(self):
        # Search through all the farms in the Surveyor General list
        found_farms = list(filter(lambda x: re.search(self.location, x[1].strip()), self.farms))
        if found_farms:
            if len(found_farms) == 1:
                self.notes = "Farm matched exactly in Surveyor General list. Matched farm = " + found_farms[0][1]
                self.lat = found_farms[0][4]
                self.long = found_farms[0][5]
            else:
                found_farms = min(found_farms, key=lambda x: sqrt((pow(float(x[4]) - self.original_lat, 2) + pow(float(x[5]) - self.original_long, 2))))
                self.notes = "Multiple farms matched in Surveyor General list. Closest farm = " + found_farms[1]
                self.lat = found_farms[4]
                self.long = found_farms[5]
            return

        # Fuzzy match through all the farms in the Surveyor General list
        # Some farm names are too common to do fuzzy matching, basically anything with 'fontein'/'fountain'
        if re.search(r'fou?nt[ae]in', self.location, re.IGNORECASE) is None:
            # Let's try some fuzzy matching
            # Can't work out a better way of doing this, so put the farm names into a temp var
            temp = []
            for f in self.farms:
                temp.append(f[1].strip())
            results = process.extractOne(self.location, temp)

            # If we match greater than 88% or 50% with the right QDS let's call it
            matchedFarm = self.farms[temp.index(results[0])]
            if results[1] > 88:
                self.notes = "Fuzzy matching using Surveyor General list. Best match = " + results[0] + " with 88+ accuracy"
                self.lat = matchedFarm[4]
                self.long = matchedFarm[5]
            elif results[1] > 50 and self.original_qds[0:5] == matchedFarm[2][0:5]:
                self.notes = "Fuzzy matching using Surveyor General list. Best match = " + results[0] + " with 50+ accuracy and same QDS"
                self.lat = matchedFarm[4]
                self.long = matchedFarm[5]
            else:
                self.notes = "No farm found using Surveyor General list. Closest match " + str(results[0]) + " with certainty of " + str(results[1])
        else:
            self.notes = "No farm found using Surveyor General list, no fuzzy matching as name is too common"

    def _is_park(self):
        '''
        Works out whether this location is in a park or nature reserve
        '''
        return re.match('(National\s+Park|Nature\s+Reserve)', self.location, re.IGNORECASE)

    def _get_directions(self):
        main_regex = '\s*(\d\d*[,\.]?\d*)\s*(k?m|miles)\s+(([swne]{1,3})|south|no?rth|east|west)\s*(of|fro?m)?\s*'

        # If there's something in front of it and something behind it, i.e., ^muizenberg, 20 km s of tokai$
        # we really don't want to use the directions then, rather use the main thing and strip out the rest
        m = re.search(r'^(.+?)' + re.escape(main_regex) + '(.+)$', self.location, re.IGNORECASE)
        if m:
            self.location = m.group(1)
            return

        # Second case: There's something behind it, i.e., ^40 km w from muizenberg
        m = re.search(r'^' + re.escape(main_regex) + '(.+)$', self.location, re.IGNORECASE)
        if m:
            self.directions['distance'] = m.group(1)
            self.directions['measurement'] = m.group(2)
            self.directions['direction'] = m.group(3)
            self.location = m.group(5)
        else:
            # Third case: There's something in front of it, i.e., muizenberg 40km w$
            m = re.search(r'^(.+?)' + re.escape(main_regex) + '$', self.location, re.IGNORECASE)
            if m:
                self.location = m.group(1)
                self.directions['distance'] = m.group(2)
                self.directions['measurement'] = m.group(3)
                self.directions['direction'] = m.group(4)
            else:
                self.location = re.sub(main_regex, ' ', self.location, flags=re.IGNORECASE)



