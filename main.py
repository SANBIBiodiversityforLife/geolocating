'''
The following script iterates through an input csv and creates a geolocated location for each row
It then prints the output in an output.csv
'''

# Import the relevant libraries
import csv
from location import Location, Provinces, FeatureTypes

# Change the province to geolocate other provinces
province = Provinces.kwazulu_natal
input_csv = 'data_to_geolocate/' + province.name + '.csv'

# Collect all of the databases we will use for geolocating
databases = []

# The farms.csv contains a list of farms in SA with their coordinates from the Surveyor General in Wynberg
farms_all = list(csv.reader(open('surveyor_general.csv')))
farms = []
for entry in farms_all:
    if entry[6] in province.value:
        farms.append(Location(db_id=entry[0], qds=entry[3].strip(), priority=1, lat=float(entry[4]),
                              long=float(entry[5]), location=entry[1].strip(), province=province,
                              feature_type=FeatureTypes.farm, source="Farms"))
#databases.append({"db": farms, "feature_type": FeatureTypes.farm, "name": "Farms"})

# The gazetteer_all has multiple sources which need prioritising
gazetteer_all = list(csv.reader(open('gazetteer.csv')))
gazetteer_source_priorities = list(csv.reader(open('gazetteer_source_priorities.csv')))
gazetteer_source_priorities.sort(key=lambda x: x[3])
gazetteer = []
i = 0
for entry in gazetteer_all:
    #if entry[2] in province.value:
    # Skip the first one, or if they haven't got a lat or long
    if i == 0 or entry[7].strip() == '' or entry[6].strip() == '':
        i += 1
        continue
    try:
        g = Location(db_id=entry[0], qds=entry[3].strip(), province=province,
                     source="Gazetteer - " + [x[0] for x in gazetteer_source_priorities if x[4] == entry[8]][0],
                     priority=int([x[3] for x in gazetteer_source_priorities if x[4] == entry[8]][0]),
                     lat=float(entry[7].strip()), long=float(entry[6].strip()), location=entry[1].strip())
    except:
        print(entry)
        continue

    gazetteer.append(g)
databases.append({"db": gazetteer, "feature_type": FeatureTypes.unknown, "name": "Gazetteer"})

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
              'new_locality'
              'latitude',
              'longitude',
              'precision',
              'google_maps_link',
              'notes']
output_csv = 'output.csv'
with open(output_csv, 'w', newline='') as newFile:
    writer = csv.DictWriter(newFile, fieldnames=fieldnames)
    writer.writeheader()

# Run through the input file
with open(input_csv, newline='') as csv_file:
    line_reader = csv.DictReader(csv_file, delimiter=',', quotechar='"')

    # Iterate over each location
    for line in line_reader:
        qds = line['Locus'].strip()
        print('--')
        print(line['Locality'])

        # Get the original lat/long and raise an error if the QDS is weird
        try:
            lat = -1 * float(qds[0] + qds[1])
            long = float(qds[2] + qds[3])
        except:
            print('ERROR with the qds ' + str(qds))
            raise

        # Create a geolocated location object
        locality = Location(province=province, qds=qds, lat=lat, long=long, location=line['Locality'].strip())
        temp = locality.geolocate(databases, google=google_geolocator)

        # Write the location object to the output csv
        if temp:
            print(temp.location)
            fieldnames = ['original_locality',
              'original_qds',
              'new_locality'
              'latitude',
              'longitude',
              'precision',
              'google_maps_link',
              'notes']
            with open(output_csv, 'a', newline='') as newFile:
                writer = csv.writer(newFile, skipinitialspace=True)
                writer.writerow([line['Locality'],
                                 qds,
                                 temp.location,
                                 temp.lat,
                                 temp.long,
                                 '',
                                 'http://www.google.co.za/maps/place/' + str(temp.lat) + ',' + str(temp.long),
                                 temp.notes])
        else:
            print("Could not find location")
