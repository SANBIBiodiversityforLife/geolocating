import re, sys
from fuzzywuzzy import process
from math import pow, sqrt, cos, radians
from enum import Enum


class FeatureTypes(Enum):
    '''
    Geographical feature types
    '''
    town = 'town'
    mountain = 'mountain'
    railway = 'railway'
    farm = 'farm'
    park = 'park'
    unknown = 'unknown'


class Provinces(Enum):
    '''
    The provinces of SA
    '''
    northern_cape = ['NC', 'Northern Cape', 'SAF-NC']
    free_state = ['F', 'Free State', 'FS', 'SAF-FS']
    gauteng = ['Gauteng', 'Gauteng & Mphum', 'Gautng or Lstho', 'SAF-GA', 'GP', 'SAF-TV']
    kwazulu_natal = ['K-N', 'KwaZulu-Natal', 'KZ', 'KZN', 'SAF-KN']
    limpopo = ['Lim', 'Limpopo', 'Lm', 'LP', 'NP', 'Northern Provin', 'Northern Province', 'SAF-LP', 'SAF-TV']
    mpumalanga = ['MP', 'Mpumalanga', 'SAF-MP', 'SAF-TV']
    north_west = ['North West', 'North-West', 'NW', 'SAF-NW', 'SAF-TV']
    western_cape = ['WC', 'Western Cape', 'WP', 'SAF-CP', 'SAF-WC']
    eastern_cape = ['SAF-EC', 'Eastern Cape', 'Eastern Cape?', 'EC']


class Location:
    def __init__(self, province, location, lat, long, qds, priority=0, db_id=0, source='', farm_number=0,
                 feature_type=FeatureTypes.unknown, notes=''):
        # These make up the core of a location
        self.province = province
        self.qds = qds
        self.lat = lat
        self.long = long
        self.location = location

        # These are additional variables
        self.db_id = db_id
        self.priority = priority
        self.source = source
        self.feature_type = feature_type
        self.farm_number = farm_number
        self.notes = notes

    def geolocate(self, databases, google):  # parks, farms, gazetteer, google):
        '''
        The set of steps we run through to try and geolocate a string
        '''
        # Clean the location string
        self._clean_location()

        # If the loc is x km from something etc then try and get the location and clean the location string further
        directions = self._get_directions()

        # Check and see if it's a farm and clean up the name a bit more
        if self._is_farm():
            self.feature_type = FeatureTypes.farm

        # Does this cleaned location string contain something?
        if self.location.strip() is '':
            if self.lat is not None and self.long is not None:
                return self
            # else:
            # TODO if loc is blank then it needs to get the center from Fhatani's script (input qds) which he still has to write
            # But wait, can't we just use the original lat/long?
            return

        # Try and see if we can find this location in one of the databases
        for database in databases:
            print("trying " + database["name"])
            geolocated_location = self._geolocate_using_db(database["db"])
            if geolocated_location:
                self.feature_type = database["feature_type"]
                self.source = database["name"]
                if directions:
                    print('lat: ' + str(geolocated_location.lat) + ' long: ' + str(geolocated_location.long))
                    geolocated_location._apply_directions(directions)
                    print('lat: ' + str(geolocated_location.lat) + ' long: ' + str(geolocated_location.long))
                return geolocated_location

        # If all else fails, try google
        geolocated_location = self._geolocate_using_google(google)
        if directions:
            geolocated_location._apply_directions(directions)
        return geolocated_location

    def _geolocate_using_db(self, db):
        # If we get a farm number try and get the location based on that (if we can't then continue on)
        if self.farm_number:
            matched_locations = list(filter(lambda x: re.search(str(self.farm_number), db.location), db))
            best_matched_location = self._get_best_matched_location(matched_locations)
            if best_matched_location:
                return best_matched_location

        # Get a simple list of the location strings to use in the fuzzy matching
        db_location_names = [x.location.strip() for x in db]

        # Get the top matched locations in the same qds
        results = process.extractBests(self.location, db_location_names, score_cutoff=90)

        # If there aren't any then return false
        if not results:
            return False

        # Otherwise convert back from simple names to full Location objects
        matched_locations = [db[db_location_names.index(x[0])] for x in results]

        # Return the best match
        return self._get_best_matched_location(matched_locations)

    def _get_best_matched_location(self, matched_locations):
        # If there are some locations in the correct qds then keep them and discard the others
        locations_in_correct_qds = [x for x in matched_locations if x.qds[0:5] == self.qds[0:5]]
        if locations_in_correct_qds:
            matched_locations = locations_in_correct_qds

        # Take results from only the most trustworthy/prioritised source
        best_priority_score = min([x.priority for x in matched_locations])
        matched_locations = [x for x in matched_locations if x.priority == best_priority_score]

        # If there are any with the right feature types then keep them and discard the others
        if self.feature_type:
            correct_type_locations = [x for x in matched_locations if x.feature_type == self.feature_type or
                                      x.feature_type == FeatureTypes.unknown]
            if correct_type_locations:
                matched_locations = correct_type_locations

        # else:
            # most_likely_feature = min(x.feature_type for x in )
            # TODO

        # Finally, choose the one closest to the original location
        return min(matched_locations, key=lambda x: self._get_km_distance_from_two_points(x.lat, x.long))

    def _geolocate_using_google(self, google_geolocator):
        try:
            province_name = self.province.name.replace("_", " ").capitalize()
            results = google_geolocator.geocode(query=self.location + ', ' + province_name, region='za')

            # Has it actually managed to find coords beyond province level? and are we in the right country?
            country = ''
            for address_component in results.raw['address_components']:
                if address_component['types'] == ['country', 'political']:
                    country = address_component['short_name']

            if str(results) != province_name + ", South Africa" and country == 'ZA':
                self.lat = results.raw['geometry']['location']['lat']
                self.long = results.raw['geometry']['location']['lng']
                # We are finding the difference in x and y between a point (i.e., x degrees)
                self.notes = "Google maps API geolocates this as: " + results.raw['geometry']['location_type'] + \
                             " - distance from original qds = " + self._get_km_distance_from_two_points(self.lat, self.long)
                return self
        except AttributeError as e:
            print("Google maps could not find :" + self.location + ' gives error : ' + str(sys.exc_info()))
            return False
        except:
            print("ANOTHER ERROR occurred when looking up in google " + str(sys.exc_info()))
            return False
            # At this stage perhaps we should run it through bing or another map.

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
            return False

        # There's something behind it, i.e., ^40 km w from muizenberg
        m = re.search(r'^' + main_regex + '(.+)$', self.location, re.IGNORECASE)
        if m:
            self.location = m.group(6)
            return {'distance': float(m.group(1)), 'measurement': m.group(2).strip().lower(), 'direction': m.group(3).strip().lower()}
        else:
            # There's something in front of it, i.e., muizenberg 40km w$
            m = re.search(r'^(.+?)' + re.escape(main_regex) + '$', self.location, re.IGNORECASE)
            if m:
                self.location = m.group(1)
                return {'distance': float(m.group(2)), 'measurement': m.group(3).strip().lower(), 'direction': m.group(4).strip().lower()}
            else:
                self.location = re.sub(main_regex, ' ', self.location, flags=re.IGNORECASE)
                return False

    def _apply_directions(self, directions):
        # Convert everything to KM
        #import pdb; pdb.set_trace()
        if directions['measurement'] in ['m', 'meters', 'metres']:
            directions['distance'] = directions['distance'] / 1000
        elif directions['measurement'] in ['mi', 'miles']:
            directions['distance'] = directions['distance'] * 1.60934
        # Convert the decimal degrees to radians
        if directions["direction"] in ['s', 'south']:
                self.lat = self.lat - (directions['distance'] * (1/110.54))
                return True
        if directions["direction"] in ['n', 'north']:
                self.lat = self.lat + (directions['distance'] * (1/110.54))
                return True

        if directions["direction"] in ['e', 'east']:
                self.long = self.long + (directions['distance'] * 1/(cos(self.lat) * 111.320))
                return True
        if directions["direction"] in ['w', 'west']:
                self.long = self.long - (directions['distance'] * 1/(cos(self.lat) * 111.320))
                return True

    def _apply_directions(self, directions):
        # Convert everything to KM
        #import pdb; pdb.set_trace()
        if directions['measurement'] in ['m', 'meters', 'metres']:
            directions['distance'] = directions['distance'] / 1000
        elif directions['measurement'] in ['mi', 'miles']:
            directions['distance'] = directions['distance'] * 1.60934
        # Convert the decimal degrees to radians
        if directions["direction"] in ['s', 'south']:
                self.lat = radians(self.lat)
                return True
        if directions["direction"] in ['n', 'north']:
                self.lat = radians(self.lat)
                return True

        if directions["direction"] in ['e', 'east']:
                self.long = self.long + (directions['distance'] * 1/(cos(self.lat) * 111.320))
                return True
        if directions["direction"] in ['w', 'west']:
                self.long = self.long - (directions['distance'] * 1/(cos(self.lat) * 111.320))
                return True




        # Complicated stuff
        if directions["direction"] in ['se', 'southeast', 'south-east', 'south east']:
                directions["direction"] = ['south', 'east']
        if directions["direction"] in ['ne', 'northeast', 'north-east', 'north east']:
                directions["direction"] = ['north', 'east']
        if directions["direction"] in ['nw', 'northwest', 'north-west', 'north west']:
                directions["direction"] = ['north', 'west']
        if directions["direction"] in ['sw', 'southwest', 'south-west', 'south west']:
                directions["direction"] = ['south', 'west']

        for direction in directions:
            if direction in ['s', 'south']:
                    self.lat = self.lat - (directions['distance'] * (1/110.54))
            if direction in ['n', 'north']:
                    self.lat = self.lat + (directions['distance'] * (1/110.54))
            if direction in ['e', 'east']:
                    self.long = self.long + (directions['distance'] * 1/(cos(self.lat) * 111.320))
            if direction in ['w', 'west']:
                    self.long = self.long - (directions['distance'] * 1/(cos(self.lat) * 111.320))
        return True

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
        phrases = ['along the top of', 'at the bottom of', 'nearby', 'next to', 'in someone']
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

    def _get_km_distance_from_two_points(self, a_lat, a_long, b_lat=None, b_long=None):
        if b_lat is None:
            b_lat = self.lat
        if b_long is None:
            b_long = self.long
        lat_distance = (float(a_lat) - b_lat) * 110.54
        long_distance = 111.32 * cos(float(a_long) - b_long)
        return sqrt((pow(lat_distance, 2) + pow(long_distance, 2)))


class FarmLocation(Location):
    def __init__(self, farm_number=0):
        super(Location, self).__init__()
        self.farm_number = farm_number
