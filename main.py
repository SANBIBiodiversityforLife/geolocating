# Customisable variables - change these to fit the province/user
province = 'Northern Cape'
province_f = province.replace(" ", "").lower()
precisionBy = 'johaadienr'

# Import the relevant libraries
import csv
import re
# from geopy.geocoders import ArcGIS < This one times out
# from geopy.geocoders import Bing < requires api key
# from geopy.geocoders import YahooPlaceFinder < requires api key
# from geopy.geocoders import Nominatim < service times out
from geopy.geocoders import GoogleV3
from fuzzywuzzy import process
from math import pow, sqrt
import sys

# Import our custom functions
import functions as myfs

# These are the project variables
geolocate = GoogleV3()
inputcsv = province_f + "/input.csv"
outputcsv = province_f + "/output.csv"
fieldnames = ['original_locality', 'original_qds', 'latitude', 'longitude', 'precision', 'precby', 'correctedaddress', 'gmapslink', 'farm']
gmapsprefix = 'http://www.google.co.za/maps/place/'
farms = list(csv.reader(open(province_f + '/farms.csv')))
gaz = list(csv.reader(open('GazetteerForSANBI.csv')))

# Write the headers for the new file first
with open(outputcsv, 'w', newline='') as newFile:
    writer = csv.DictWriter(newFile, fieldnames=fieldnames)
    writer.writeheader()

# Open the old file and start running through it
with open(inputcsv, newline='') as csvFile:
    lineReader = csv.DictReader(csvFile, delimiter=',', quotechar='"')

    # Iterate over each locality to look up
    for line in lineReader:
        farm, lat, lng, precision = [0] * 4
        loc = myfs.cleanedloc(line["Locality"])
        qds = line["Locus"].strip()


        if strip(loc) is '':
            # TODO if loc is blank then it needs to get the center from Fhatani's script (input qds) which he still has to write
            # Write out the CSV
            # writeoutput(writer, )
            pass # one day this must be continue

        # If the loc is x km from something etc then try and get the location with any of the below formulas, and at the end
        # it needs to add/subtract from the lat and long
        loc = myfs.getdirections(loc)
        directions = loc["directions"]
        loc = loc["locality"]

        # We work out whether it is a park from the cleanedloc function
        ispark = loc["ispark"]
        loc = loc["locality"]

        # What is Rukaya doing here?
        try:
            origLat = -1 * float(qds[0] + qds[1])
            origLng = float(qds[2] + qds[3])
        except:
            print('ERROR with the qds ' + str(qds))
            raise

        # Check to see if we recognise it as a farm
        farmName = myfs.getfarmname(loc)
        if farmName:
            farm = "This is a farm"
            precision = "FARMPRECISION"

            # Clean the loc text specifically for farms
            loc = myfs.cleanedfarm(loc)

            # Look up the farm and flag it if it's not found
            farmString = re.compile(farmName, re.IGNORECASE)
            foundFarms = list(filter(lambda x: farmString.search(x[1].strip()), farms))

            if foundFarms:
                if len(foundFarms) == 1:
                    farm = "Farm matched exactly"
                    lat = foundFarms[0][4]
                    lng = foundFarms[0][5]
                    results = foundFarms[0][1]
                else:
                    # Shit, we have multiple farms found. Get the one nearest the qds
                    foundFarm = min(foundFarms, key=lambda x: sqrt((pow(float(x[4]) - origLat, 2) + pow(float(x[5]) - origLng, 2))))
                    farm = "Multiple farms found"
                    lat = foundFarm[4]
                    lng = foundFarm[5]
                    results = foundFarm[1]
            else:
                # Some farm names are too common to do fuzzy matching, basically anything with 'fontein'/'fountain'
                if re.search(r'fou?nt[ae]in', farmName, re.IGNORECASE) is None:
                    # Let's try some fuzzy matching
                    farmNames = []
                    for f in farms:
                        farmNames.append(f[1].strip())
                    results = process.extractOne(farmName, farmNames)

                    # If we match greater than 88% or 50% with the right QDS let's call it
                    matchedFarm = farms[farmNames.index(results[0])]
                    if results[1] > 88:
                        farm = "Farm matched is " + results[0] + " with 88+ accuracy"
                        lat = matchedFarm[4]
                        lng = matchedFarm[5]
                        results = results[0]
                    elif results[1] > 50 and qds[0:5] == matchedFarm[2][0:5]:
                        farm = "Farm matched is " + results[0] + " with 50+ accuracy and same QDS"
                        lat = matchedFarm[4]
                        lng = matchedFarm[5]
                        results = results[0]
                    else:
                        farm = "No farm found"
                        results = "Closest match " + str(results[0]) + " with certainty of " + str(results[1])
                else:
                    farm = "No farm found, no fuzzy matching as name is too common"
                    results = ""
        elif ispark:
            # TODO Fhatani will add a list of all parks and iterate over them
            pass
        else:
            try:
                if qds:
                    results = geolocate.geocode(query=loc + ', ' + province, region='za')
                else:
                    results = geolocate.geocode(query=loc + ', ' + province, region='za')

                # Has it actually managed to find coords beyond province level? and are we in the right country?
                gCountry = ''
                for addresscomponent in results.raw['address_components']:
                    if addresscomponent['types'] == ['country', 'political']:
                        gCountry = addresscomponent['short_name']

                if str(results) != province + ", South Africa" and gCountry == 'ZA':
                    lat = results.raw['geometry']['location']['lat']
                    lng = results.raw['geometry']['location']['lng']
                    precision = results.raw['geometry']['location_type']
                    # We are finding the difference in x and y between a point (i.e., x degrees)
                    farm = pow(float(lat) - origLat, 2) + pow(float(lng) - origLng, 2)
                    # a ^ 2 + b ^ 2 = c ^ 2 !!!
                    farm = "Distance from original qds: " + str(sqrt(farm))
                # else:
                    # Try it without bounding, maybe clean the loc a bit more too?
                    # results = geolocate.geocode(query=loc + ', ' + province, region='za')
            except AttributeError as e:
                print("Google maps could not find :" + loc + ' gives error : ' + str(sys.exc_info()))
                print(" bounds : " + str(myfs.convertqds(qds)))
                results = 0
            except:
                print("ANOTHER ERROR occurred when looking up in google " + str(sys.exc_info()))
                # At this stage perhaps we should run it through bing or another map.

        # If this locality has directions then try and calculate a new lat long based on the directions
        # TODO Rukaya or Fhatani

        with open(outputcsv, 'a', newline='') as newFile:
            writer = csv.writer(newFile, skipinitialspace=True)
            if lat != 0:
                googleMapsLink = gmapsprefix + str(lat) + ',' + str(lng)
            else:
                googleMapsLink = ''

            # Write out the CSV
            myfs.writeoutput(writer, [line["Locality"],
                             qds,
                             str(lat),
                             str(lng),
                             str(precision),
                             precisionBy,
                             str(results),
                             googleMapsLink,
                             str(farm)])