import re, sys
from fuzzywuzzy import process
from math import pow, sqrt, cos, radians
from enum import Enum
from geopy import Point
from geopy.distance import distance, VincentyDistance


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
        if directions:
            print(directions)

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

        # Try and get decimal degrees (e.g.,  31d38m43sS 20d24m57sE from the string if it exists use that as lat long)
        if self._contains_degrees_in_location():
            print('Found lat long in location: ' + self.lat + ' ' + self.long + ' ' + self.location)
            return self

        # Try and see if we can find this location in one of the databases
        for database in databases:
            geolocated_location = self._geolocate_using_db(database["db"])
            if geolocated_location:
                self.feature_type = database["feature_type"]
                self.source = database["name"]
                if directions:
                    geolocated_location._apply_directions(directions)
                return geolocated_location

        # If all else fails, try google
        geolocated_location = self._geolocate_using_google(google)
        if directions:
            geolocated_location._apply_directions(directions)
        return geolocated_location

    def _contains_degrees_in_location(self):
        regex = '\s[sS][\s\.](\d\d)[\s\.d](\d\d)[\s\.m](\d\d)(\.\d+)?s?\s*,?\s*[eE][\s\.](\d\d)[\s\.d](\d\d)[\s\.m](\d\d)(\.\d+)?s?\s'
        match = re.search(regex, self.location)
        if match:
            south = {'degrees': float(match.group(1)), 'minutes': float(match.group(2)), 'seconds': float(match.group(3))}
            east = {'degrees': float(match.group(5)), 'minutes': float(match.group(6)), 'seconds': float(match.group(7))}
            self.latitude = south['degrees'] + south['minutes'] / 60 + south['seconds'] / 3600
            self.longitude = east['degrees'] + east['minutes'] / 60 + east['seconds'] / 3600
            return True
        else:
            return False

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
        # If there's something in front of it and something behind it, i.e., ^muizenberg, 20 km s of tokai$
        # we really don't want to use the directions then, rather use the main thing and strip out the rest
        main_regex = '\s*(\d\d*[,\.]?\d*)\s*(k?m|miles)\s+(([swne]{1,3})|south|no?rth|east|west)\s*(of|fro?m)?\s*'
        m = re.search(r'^(.+?)' + re.escape(main_regex) + '(.+)$', self.location, re.IGNORECASE)
        if m:
            self.location = m.group(1)
            return False

        # We store the location variable and try and substitute stuff in it
        location = self.location

        # Look for digits and measurement units
        measurement_units = {'miles': ['miles', 'mile', 'mi'],
                             'yards': ['yard', 'yards'],
                             'kilometers': ['km', 'kmeters', 'kmetres', 'kilometers', 'kmeter', 'kms', 'kmetre', 'kilometer'],
                             'meters': ['m', 'meters', 'metres', 'meter', 'metre', 'ms'],
                             'feet': ['ft', 'feet']}
        distance = 0
        measurement = ''
        for name, variations in measurement_units.items():
            for v in variations:
                regex = '\s*(\d\d*[,\.]?\d*)\s*(' + v + ')'
                substitute = re.search(regex, location, re.IGNORECASE)
                temp = re.sub(regex, '', location, re.IGNORECASE)
                if temp is not location:
                    distance = float(substitute.group(1))
                    measurement = name
                    if variations == measurement_units['miles']:
                        distance *= 1.60934
                    elif variations is measurement_units['meters']:
                        distance *= 1000
                    elif variations is measurement_units['feet']:
                        distance *= 3280.84
                    elif variations is measurement_units['yards']:
                        distance *= 1093.61
                    location = temp
                    break

        # Look for bearings, keep track of the ones we need to remove and get rid of them afterwards
        bearings_matches = {'south': ['south', 's', 'se', 'sw', 'south-east', 'southeast', 'south-west', 'southwest'],
                            'north': ['north', 'n', 'ne', 'nw', 'north-east', 'northeast', 'north-west', 'northwest'],
                            'east': ['east', 'e', 'se', 'ne', 'south-east', 'southeast', 'north-east', 'northeast'],
                            'west': ['west', 'w', 'sw', 'nw', 'south-west', 'southwest', 'north-west', 'northwest']}
        bearings = []
        strings_to_remove = set()  # apparently keeps unique values only
        for proper_name, match_list in bearings_matches.items():
            for match in match_list:
                regex = '\s(' + match + ')\.?(\s|$)'
                temp = re.sub(regex, '', location, flags=re.IGNORECASE)
                if temp is not location:
                    bearings.append(proper_name)
                    strings_to_remove.add(regex)

        # Remove all of the applicable bearings
        for regex in strings_to_remove:
            location = re.sub(regex, '', location, flags=re.IGNORECASE)

        # If we have bearings and distance and measurement we can make a sensible set of directions to return
        if bearings and distance and measurement:
            # Clean up the location string
            location = re.sub('([oO]f|[fF]ro?m)', '', location)
            location = re.sub('^\s*[\.,;]', '', location)
            location = re.sub('\s*[\.,;]$', '', location)
            self.location = location.strip()
            return {'bearings': bearings, 'distance': distance}
        else:
            return False

    def _apply_directions(self, directions):
        for bearing in directions['bearings']:
            # Convert the bearing into something VincentyDistance understands:
            if bearing == 'south':
                bearing_degrees = 180
            elif bearing == 'north':
                bearing_degrees = 0
            elif bearing == 'east':
                bearing_degrees = 90
            else:
                bearing_degrees = 270

            # Define starting point.
            start = Point(self.lat, self.long)

            # Use the `destination` method with a bearing of 0 degrees (which is north)
            # in order to go from point `start` 1 km to north.
            destination = VincentyDistance(kilometers=directions['distance']).destination(start, bearing_degrees)
            self.lat = destination.latitude
            self.long = destination.longitude
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
