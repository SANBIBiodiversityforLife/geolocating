# Import the relevant libraries
import csv
import location
from geopy.geocoders import GoogleV3
# from geopy.geocoders import ArcGIS < This one times out
# from geopy.geocoders import Bing < requires api key
# from geopy.geocoders import YahooPlaceFinder < requires api key
# from geopy.geocoders import Nominatim < service times out

province = "Northern Cape"
province_formatted = province.replace(" ", "").lower()
fieldnames = ['original_locality',
               'original_qds',
               'latitude',
               'longitude',
               'precision',
               'source',
               'corrected_address',
               'google_maps_link',
               'notes']

input_csv = province_formatted + "/input.csv"
output_csv = province_formatted + "/output.csv"

# The following are the different dbs available
farms = list(csv.reader(open(province_formatted + '/farms.csv')))
gazetteer = list(csv.reader(open('GazetteerForSANBI.csv')))
google_geolocator = GoogleV3()

# Write the headers to the output file
with open(output_csv, 'w', newline='') as newFile:
    writer = csv.DictWriter(newFile, fieldnames=fieldnames)
    writer.writeheader()

# Run through the input file
with open(input_csv, newline='') as csvFile:
    lineReader = csv.DictReader(csvFile, delimiter=',', quotechar='"')

    # Iterate over each location
    for line in lineReader:
        qds = line["Locus"].strip()

        # Get the original lat/long and raise an error if the QDS is weird
        try:
            lat = -1 * float(qds[0] + qds[1])
            long = float(qds[2] + qds[3])
        except:
            print('ERROR with the qds ' + str(qds))
            raise

        locality = location.Location(province=province, qds=qds, lat=lat, long=long, location=line["Locality"],
                                     farms=farms, gazetteer=gazetteer, google_geolocator=google_geolocator)

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

