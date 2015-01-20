import re
from fuzzywuzzy import process
from math import pow, sqrt, cos
from enum import Enum


class Provinces(Enum):
    northern_cape = 'Northern Cape'
    free_state = 'Free State'
    gauteng = 'Gauteng'
    kwazulu_natal = 'Kwazulu-Natal'
    limpopo = 'Limpopo'
    mpumalanga = 'Mpumalanga'
    north_west = 'North West'
    western_cape = 'Western Cape'
    eastern_cape = 'Eastern Cape'


class Location:
    '''
    A location string with its latitude and longitude
    '''

    def __init__(self, province='', qds='', lat='', long='', location='', farms=[], gazetteer=[], google_geolocator=None):
        '''
        Set up the variables used in this object
        '''
        # Some info about the item we want to geolocate
        self.province = province
        self.original_qds = qds
        self.original_lat = float(lat)
        self.original_long = float(long)
        self.location = location

        # These are databases/api tools to help us geolocate stuff
        self.farms = farms
        self.farm_names = [x[1].strip() for x in farms]
        self.gazetteer = gazetteer
        self.gazetteer_names = [x[1].strip() for x in gazetteer]
        self.google_geolocator = google_geolocator

        # Our geolocate info in some variables
        self.directions = {'direction': '', 'distance': '', 'measurement': ''}
        self.new_lat = 0
        self.new_long = 0
        self.farm_number = 0
        self.notes = ''
        self.gazetteer_lat = 0
        self.gazetteer_long = 0
        self.geolocation_source = None

        # Run the main string of logic to geolocate this baby!
        self._geolocate()

    def _geolocate(self):
        '''
        The set of steps we run through to try and geolocate a string
        '''
        print("----\n" + self.location)
        # Clean the location string
        self._clean_location()

        # If the loc is x km from something etc then try and get the location and clean the location string further
        self._get_directions()

        # Does this cleaned location string contain something?
        if self.location.strip() is '':
            # TODO if loc is blank then it needs to get the center from Fhatani's script (input qds) which he still has to write
            # But wait, can't we just use the original lat/long?
            return

        print(self.location)
        # Try and see if we can find this location in a list of the parks
        if self._geolocate_park():
            self.geolocation_source = "National parks list"
            return

        # Otherwise, is this location a farm? This isn't a foolproof method, so we need to run it again if we can't
        # find anything in the gazetteer or using google's api
        if self._is_farm():
            if self._geolocate_surveyor_general_farms():
                self.geolocation_source = "Surveyor general farms"
            else:
                # TODO add les' database farm processing
                self.notes = "This is a farm but it could not be found in the gazetteer"
                self.geolocation_source = "Gazetteer - "

        # Ok it's not a special thing like a park or a farm, so let's try the gazetteer and google
        self._geolocate_gazetteer()
        self._geolocate_google()

    def _geolocate_gazetteer(self):
        # Get all of the matched locations
        matched = list(filter(lambda x: re.search(self.location, x[1].strip()), self.gazetteer))

        #
        import pdb; pdb.set_trace()
        pass

    def _geolocate_park(self):
        # TODO Fhatani will add a list of all parks and iterate over them
        return False

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
                self.notes = "Google maps API geolocates this as: " + results.raw['geometry']['location_type'] + \
                             " - distance from original qds = " + self._get_km_distance_from_original_location()
                # a ^ 2 + b ^ 2 = c ^ 2 !!!
            # else:
                # Try it without bounding, maybe clean the loc a bit more too?
                # results = geolocate.geocode(query=loc + ', ' + province, region='za')
        except AttributeError as e:
            print("Google maps could not find :" + self.location + ' gives error : ' + str(sys.exc_info()))
        except:
            print("ANOTHER ERROR occurred when looking up in google " + str(sys.exc_info()))
            # At this stage perhaps we should run it through bing or another map.

    def _geolocate_surveyor_general_farms(self):
        # Search through all the farms in the Surveyor General list without fuzzy matching
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
            return True

        # Fuzzy match through all the farms in the Surveyor General list
        # Some farm names are too common to do fuzzy matching, basically anything with 'fontein'/'fountain'
        if re.search(r'fou?nt[ae]in', self.location, re.IGNORECASE) is None:
            # Get the top 5 fuzzy matched farms
            results = process.extractBests(self.location, self.farm_names, limit=5, score_cutoff=70)
            if results:
                matched_farms = []
                for result in results:
                        matched_farms.append(self.farms[self.farm_names.index(result[0])])

                # Which of those is the closest to the original lat long?
                closest_matched_farm = min(matched_farms, key=lambda x: self._get_km_distance_from_original_location(x[4], x[5]))

                if matched_farms[0] is not closest_matched_farm:
                    self.notes = "Farm fuzzy matched (" + matched_farms[0][1] + \
                                 ") through SG, best match different to closest farm to original lat long, which is = " + closest_matched_farm[1]
                else:
                    self.notes = "Farm fuzzy matched (" + matched_farms[0][1] + ") though SG"

                # Set the lat and long
                self.lat = closest_matched_farm[0][4]
                self.long = closest_matched_farm[0][5]
                print(self.notes)

                return True

        # Can't find a farm!
        self.notes = "No farm found using Surveyor General list."
        return False

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

        # There's something behind it, i.e., ^40 km w from muizenberg
        m = re.search(r'^' + main_regex + '(.+)$', self.location, re.IGNORECASE)
        if m:
            self.directions['distance'] = m.group(1)
            self.directions['measurement'] = m.group(2)
            self.directions['direction'] = m.group(3)
            self.location = m.group(6)
        else:
            # There's something in front of it, i.e., muizenberg 40km w$
            m = re.search(r'^(.+?)' + re.escape(main_regex) + '$', self.location, re.IGNORECASE)
            if m:
                self.location = m.group(1)
                self.directions['distance'] = m.group(2)
                self.directions['measurement'] = m.group(3)
                self.directions['direction'] = m.group(4)
            else:
                self.location = re.sub(main_regex, ' ', self.location, flags=re.IGNORECASE)

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

    def _get_km_distance_from_original_location(self, lat=None, long=None):
        if lat is None:
            lat = self.lat
        if long is None:
            long = self.long
        lat_distance = (float(lat) - self.original_lat) * 110.54
        long_distance = 111.32 * cos(float(long) - self.original_long)

        return sqrt((pow(lat_distance, 2) + pow(long_distance, 2)))