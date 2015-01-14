import re

def writeoutput(writer, locality='', qds='', lat='', lng='', precision='', precisionBy='', results='', googleMapsLink='', notes=''):
    writer.writerow(locality, qds, lat, lng, precision, precisionBy, results, googleMapsLink, notes)

def getfarmname(farmname):
    '''
    Checks to see whether a string is a farm name or not

    :param farmName: string containing potential farmname
    :return: proper farmName stripped of all nonsense or false if it's not a farm
    '''
    # If it's got " in farm x" then just search for the end bit as the farm name (ignore start of string)
    farmstring = re.compile('\s+[io]n\s+farm', re.IGNORECASE)
    results = farmstring.search(farmname)
    if results:
        return farmname[results.end(0):len(farmname)].strip()
    else:
        # Otherwise do some intelligent guessing to work out which bit of the string contains the farm name
        farmstring = re.compile('farm', re.IGNORECASE)
        results = farmstring.search(farmname)
        if results:
            # Get the farm string, name is probably beforehand like "Smith Farm" or behind like "Farm Smith"
            if results.start(0) > 2:
                return farmname[0:results.start(0)].strip()
            else:
                return farmname[results.end(0):len(farmname)].strip()

        # It's also a farm if it is 0 to 3 words + a 2 to 4 digits
        farmstring = re.compile('^(([A-Za-z\-]+\s*?){1,4}),?\s?[\(\[\{]?\d{2,4}[^\.].*$', re.IGNORECASE)
        results = farmstring.search(farmname)
        if results and results.group(1):
            return results.group(1)
        else:
            return False


def cleanedloc(loc):
    '''
    Removes superfluous strings which just confuse stuff

    :param loc: a location string
    :return: loc (cleaned string), return true/false for a reserve
    '''
    park = False

    temp = loc
    loc = re.sub(r'Nat\.?\s+[pP]ark\.?', 'National Park', loc)
    loc = re.sub(r'Nat\.?\s+[rR]es\.?', 'Nature Reserve', loc)
    loc = re.sub(r'\s+N\.?\s?R\.?\s+', 'Nature Reserve', loc)
    loc = re.sub(r'\s+N(at)?\.?\s?P(ark)?\.?\s+', 'National Park', loc)
    if temp != loc:
        park = True

    # A lot of them have the string "snake collected from x", remove that
    loc = re.sub(r'^\s*[cC]ollected\s+[fF]rom\s*', '', loc)

    # Some of them have farm numbers or something?
    # loc = re.sub(r'\(\d+\)', '', loc) - removing this cus I'm doing something in the farmclean instead

    # I am not sure what this means but often things have K[letter]\d\d+ and that messes stuff up
    loc = re.sub(r'^\s+\d{3,4}K[RSTUV]\s+', '', loc)

    # Some stuff in phrases is just useless and all that comes after it, so remove
    phrases = ['along the top of', 'at the bottom of', 'nearby', 'next to']
    for phrase in phrases:
        loc = re.sub(r'\s*' + re.escape(phrase) + r'.*', '', loc)

    # A lot of things have been put in the proper address then a semi colon and random comments, so get rid of these
    loc = re.sub(r';.+$', '', loc)
    return {"locality": loc.strip(), "ispark": park}


def getdirections(loc):
    '''
    Gets the directions from a location if it can (i.e., they are sensible), otherwise strips them
    :param loc:
    :return: directions and the stripped string
    '''
    directions = {'placefrom': '', 'direction': '', 'distance': '', 'placename': '', 'measurement': ''}
    mainregex = '\s*(\d\d*[,\.]?\d*)\s*(k?m|miles)\s+([swne]{1,3}|south|no?rth|east|west)\s*(of|fro?m)\s*'

    # First case: There's something in front of it and something behind it, i.e., ^muizenberg, 20 km s of tokai$
    m = re.search(r'^(.+?)' + re.escape(mainregex) + '(.+)$', loc, re.IGNORECASE)
    if m:
        directions['placename'] = m.group(1)
        directions['distance'] = m.group(2)
        directions['measurement'] = m.group(3)
        directions['direction'] = m.group(4)
        directions['placefrom'] = m.group(6)
        loc = re.sub(r'.+?\d\d*[,\.]?\d*\s*(k?m|miles)\s+(to|of|fro?m)\s*.+$', ", ", loc, flags=re.IGNORECASE)
    else:
        # Second case: There's something behind it, i.e., ^40 km w from muizenberg
        m = re.search(r'^' + re.escape(mainregex) + '(.+)$', loc, re.IGNORECASE)
        if m:
            directions['placename'] = ''
            directions['distance'] = m.group(1)
            directions['measurement'] = m.group(2)
            directions['direction'] = m.group(3)
            directions['placefrom'] = m.group(5)
        else:
            # Third case: There's something in front of it, i.e., muizenberg 40km w$
            m = re.search(r'^(.+?)' + re.escape(mainregex) + '$', loc, re.IGNORECASE)
            if m:
                directions['placename'] = m.group(1)
                directions['distance'] = m.group(2)
                directions['measurement'] = m.group(3)
                directions['direction'] = m.group(4)
                directions['placefrom'] = ''
            else:
                loc = loc = re.sub(mainregex, ' ', loc, flags=re.IGNORECASE)

    return [directions, loc.strip()]


def cleanedfarm(loc):
    '''
    Removes superfluous strings which just confuse stuff

    :param loc: a location string
    :return: loc
    '''
    loc = re.sub(r'\s*[Oo]n\s+the\s+[Ff]arm\s*', 'Farm', loc)
    loc = re.sub(r'\(\d+\)', '', loc)
    loc = re.sub(r'(Farm.+?),.+', "\g<1>", loc)
    loc = re.sub(r'(Farm.+?)\d.+', "\g<1>", loc)
    loc = re.sub(r'...+(Farm.+?)\d.+', "\g<1>", loc)

    return loc.strip()

def convertqds(qds):
    '''
    Returns 2 latitude and lngitude pairs which denote a boundary box (north east + south west)

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

