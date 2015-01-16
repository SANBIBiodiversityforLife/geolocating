'''
The following script iterates through an input csv and creates a geolocated location for each row
It then prints the output in an output.csv
'''

# Import the relevant libraries
import csv
from location import Location, Provinces

# Change the province to geolocate other provinces
province = Provinces.northern_cape
province_folder = Provinces.northern_cape.replace(" ", "").lower()
input_csv = province_folder + '/input.csv'

# The farms.csv contains a list of farms in SA with their coordinates from the Surveyor General in Wynberg
farms = list(csv.reader(open(province_folder + '/farms.csv')))
farm_names = []
for f in farms:
    farm_names.append(f[1].strip())

# The gazetteer is Les's database and has multiple sources. We need to do some processing to make it easy to
# prioritise the data from different sources. We also only include stuff from the db in the right province.
gazetteer_source = list(csv.reader(open('GazetteerForSANBI.csv')))
gazetteer_province_names = {Provinces.eastern_cape: ['SAF-EC', 'Eastern Cape', 'Eastern Cape?', 'EC'],
                            Provinces.free_state: ['F', 'Free State', 'FS', 'SAF-FS'],
                            Provinces.gauteng: ['Gauteng', 'Gauteng & Mphum', 'Gautng or Lstho', 'SAF-GA', 'GP', 'SAF-TV'],
                            Provinces.kwazulu_natal: ['K-N', 'KwaZulu-Natal', 'KZ', 'KZN', 'SAF-KN'],
                            Provinces.limpopo: ['Lim', 'Limpopo', 'Lm', 'LP', 'NP', 'Northern Provin', 'SAF-LP', 'SAF-TV'],
                            Provinces.mpumalanga: ['MP', 'Mpumalanga', 'SAF-MP', 'SAF-TV'],
                            Provinces.northern_cape: ['NC', 'Northern Cape', 'SAF-NC'],
                            Provinces.north_west: ['North West', 'North-West', 'NW', 'SAF-NW', 'SAF-TV'],
                            Provinces.western_cape: ['WC', 'Western Cape', 'WP', 'SAF-CP', 'SAF-WC']}
gazetteer_province_names = gazetteer_province_names[province]
gazetteer = {}
with open('gazetteersourcepriorities.csv', newline='') as csv_file:
    line_reader = csv.DictReader(csv_file, delimiter=',', quotechar="'")
    for line in line_reader:
        gazetteer[line['Source_']] = {'priority': line['Trustworthiness'], 'rows':
            [x for x in gazetteer_source if x[8] == line['GazSource'] and line['PROVINCE'] in gazetteer_province_names]}

# Google maps geolocating API - https://github.com/geopy/geopy
from geopy.geocoders import GoogleV3
google_geolocator = GoogleV3()
# from geopy.geocoders import ArcGIS < This one times out
# from geopy.geocoders import Bing < requires api key
# from geopy.geocoders import YahooPlaceFinder < requires api key
# from geopy.geocoders import Nominatim < service times out

# Write the headers to the output file
fieldnames = ['original_locality',
              'original_qds',
              'latitude',
              'longitude',
              'precision',
              'source',
              'corrected_address',
              'google_maps_link',
              'notes']
output_csv = province_folder + '/output.csv'
with open(output_csv, 'w', newline='') as newFile:
    writer = csv.DictWriter(newFile, fieldnames=fieldnames)
    writer.writeheader()

# Run through the input file
with open(input_csv, newline='') as csv_file:
    line_reader = csv.DictReader(csv_file, delimiter=',', quotechar="'")

    # Iterate over each location
    for line in line_reader:
        qds = line['Locus'].strip()

        # Get the original lat/long and raise an error if the QDS is weird
        try:
            lat = -1 * float(qds[0] + qds[1])
            long = float(qds[2] + qds[3])
        except:
            print('ERROR with the qds ' + str(qds))
            raise

        # Create a geolocated location object
        locality = Location(province=province, qds=qds, lat=lat, long=long, location=line['Locality'],
                                     farms=farms, gazetteer=gazetteer, google_geolocator=google_geolocator)

        # Write the location object to the output csv
        writer.writerow(locality.location, qds, locality.lat, locality.long, 'precision', locality.source, results, googleMapsLink, notes)

# Just put this here for the moment, we're not using it but it might come in useful
def convert_qds(qds):
    '''
    Returns 2 latitude and longitude pairs which denote a boundary box (north east + south west)
    '''
    lat = qds[0] + qds[1]
    lat = float(lat)
    lng = qds[2] + qds[3]
    lng = float(lng)
    bounds = {'northeast': {'lat': 0, 'lng': 0}, 'southwest': {'lat': 0, 'lng': 0}}

    # The qds is divided up into blocks with a, b, c, decode
    firstq = qds[4]
    if firstq == 'A':
        bounds['northeast']['lat'] = lat
        bounds['northeast']['lng'] = lng + 0.5
        bounds['southwest']['lat'] = lat + 0.5
        bounds['southwest']['lng'] = lng
    if firstq == 'B':
        bounds['northeast']['lat'] = lat
        bounds['northeast']['lng'] = lng + 1
        bounds['southwest']['lat'] = lat + 0.5
        bounds['southwest']['lng'] = lng + 0.5
    if firstq == 'C':
        bounds['northeast']['lat'] = lat + 0.5
        bounds['northeast']['lng'] = lng + 0.5
        bounds['southwest']['lat'] = lat + 1
        bounds['southwest']['lng'] = lng
    if firstq == 'D':
        bounds['northeast']['lat'] = lat + 0.5
        bounds['northeast']['lng'] = lng + 1
        bounds['southwest']['lat'] = lat + 1
        bounds['southwest']['lng'] = lng + 0.5

    # We are in SA so we have to southwest negative lats
    bounds['northeast']['lat'] = bounds['northeast']['lat'] * -1
    bounds['southwest']['lat'] = bounds['southwest']['lat'] * -1

    return [bounds['southwest']['lat'], bounds['southwest']['lng'], bounds['northeast']['lat'], bounds['northeast']['lng']]

#provinces = {'northern_cape': 'Northern Cape', 'free_state': 'Free State', 'gauteng': 'Gauteng', 'kwazulu_natal': 'Kwazulu-Natal', 'limpopo': 'Limpopo', 'mpumalanga': 'Mpumalanga', 'north_west': 'North West', 'western_cape': 'Western Cape'}