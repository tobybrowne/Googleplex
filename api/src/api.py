from flask import Flask, request
from flask_cors import CORS
import json
import sqlite3
import urllib
import wikipedia
import requests
from bs4 import BeautifulSoup
import numpy as np
import math
import time

app = Flask(__name__)
CORS(app)

conn = None
cur = None

# reformats the tuple arrays returned from SQL requests into more manageable outputs
def formatSQL(tupleArray, alwaysArray=False):
    length = len(tupleArray)
 
    # when the tuple array has multiple elements formats the tuple array as a 1D array or a 2D array depending on how many elements are in each tuple
    if length > 1:
        output = []
        for tuple in tupleArray:
            if len(tuple)>1:
                array = []
                for item in tuple:
                    array.append(item)
                output.append(array)
            else:
                output.append(tuple[0])
   
    # when an empty tuple array is provided returns an empty array if alwaysArray is True, otherwise returns None
    elif length == 0:
        if alwaysArray == True:
            output=[]
        else:
            output = None
 
    # when the tuple array has a single element return the data item in an array if alwaysArray is True, otherwise returns just the data item
    else:
        tuple = tupleArray[0]
        if len(tuple)>1:
            array = []
            for item in tuple:
                array.append(item)
            output = array
            if alwaysArray == True:
                output = [output]
 
        else:
            if alwaysArray == True:
                output=[tupleArray[0][0]]
            else:
                output=tupleArray[0][0]
 
    # returns formatted data
    return output

# reformats the tuple arrays returned from SQL requests into more manageable outputs
def formatSQLdict(tupleArray, alwaysArray=False):
    length = len(tupleArray)
    dict = {}
 
    # when the tuple array has multiple elements formats the tuple array as a 1D array or a 2D array depending on how many elements are in each tuple
    if length > 1:
        output = []
        for tuple in tupleArray:
            dict[tuple[0]] = tuple[1]
   
    return dict

def getWordIDs(_query):
    # sets the query to lower case
    _query = _query.lower() 

    # removes punctuation from the query
    formattedQuery = ""
    for character in _query:
            if character.isalnum()==True or character == " ":
                formattedQuery+=character

    # splits the query into an array of words, removing empty elements caused by extra spaces
    splitQuery = formattedQuery.split(" ")
    splitQuery[:] = [x for x in splitQuery if x!=""]

    # matches each word with it's corresponding wordID (if it has one) 
    wordIDs = []
    for word in splitQuery:
        wordID = formatSQL(cur.execute("select wordID from wordTbl where word=?", (word,)).fetchall())
        if wordID != None:
            wordIDs.append(wordID)

    # returns an array of wordIDs
    return wordIDs
 
def getWidget(query):
    encodedQuery = urllib.parse.quote_plus(query)
    requestURL = "https://en.wikipedia.org/w/api.php?origin=*&action=opensearch&search="+encodedQuery
    response = urllib.request.urlopen(requestURL)
    responseJSON = json.loads(response.read())
    if len(responseJSON[3])==0:
        return ""
    wikiURL = responseJSON[3][0]
    title = responseJSON[1][0]

    page = wikipedia.page(title, auto_suggest=False)
    title = page.title
    summary = page.summary[0:420]+"..."

    page = requests.get(wikiURL).text
    soup = BeautifulSoup(page, 'html.parser')
    infobox = soup.find(class_="infobox")
    images = infobox.find_all('img')
    for image in images:
        src = image.get("src")
        imageLink = src
        break

    widgetJSON = {"title": title, "description":summary, "url": wikiURL, "image": imageLink}

    return widgetJSON

# process only happens on startup (thank god)
with open("api/resources/words.txt") as word_file:
    english_words = set(word.strip().lower() for word in word_file)

def isWord(word):
    return word.lower() in english_words


def autocorrectQuery(query):
    splitQuery = query.split(" ")

    # preliminary test because the bing API is SLOW!
    isIndexed = len(getWordIDs(query)) == len(splitQuery)
    allValid = True
    for word in splitQuery:
        # maybe add an IDF limit to indexed words to be confident they aren't website typos (perhaps keep track of word frequency)
        allValid = isWord(word) or word.isnumeric() or isIndexed # just need one of these to hit
    if allValid:
        return query

    # only correct if at least one word is wrong
    print("autocorrect check")
    api_key = "723c6db20d084447bfc279aa763fc0f9"
    endpoint = "https://api.bing.microsoft.com/v7.0/SpellCheck"
    params = {
    'mkt':'en-us',
    'mode':'spell'
    }
    headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Ocp-Apim-Subscription-Key': api_key,
    }
    data = {'text': query}

    responseJSON = requests.post(endpoint, headers=headers, params=params, data=data).json()
    corrections = responseJSON["flaggedTokens"]
    for correction in corrections:
        correctWord = correction["suggestions"][0]["suggestion"]
        originalWord = correction["token"]

        if originalWord in splitQuery:
            splitQueryNP = np.array(splitQuery)
            splitQuery = np.where(splitQueryNP==originalWord, correctWord, splitQueryNP)#
    
    correctedQuery = " ".join(splitQuery)
    return correctedQuery

def createWeightDict():
    weightDict = {}

    factorData = formatSQL(cur.execute("select factorName, defaultWeight from factorTbl").fetchall())
    
    for factorName, defaultWeight in factorData:
        weightDict[factorName] = defaultWeight

    return weightDict

def getWeights(_weights):
    weightsArray = []
    for factorName, weight in _weights.items():
        weightsArray.append(float(weight))

    # returns an array containing just the weight values
    return weightsArray

def selectRelPages(_queryIDs):
    relevantPages = []
    KWappearances = {}

    # only looks at the body text
    pageWordMatch = formatSQL(cur.execute("SELECT i.pageID, i.wordID FROM indexTbl i INNER JOIN pageTbl p ON p.pageID = i.pageID WHERE p.valid = 1 AND i.wordID in ({}) AND i.textTypeID = 1".format(",".join(map(str, _queryIDs)))).fetchall(), True)
    for pageID, wordID in pageWordMatch:
        if pageID in KWappearances:
            KWappearances[pageID]+=1
        else:
            KWappearances[pageID]=1

    # faster to have a separate loop than constantly checkin
    # if the number of keyword appearances matches the number of keywords the site is deemed as relevant
    for pageID in KWappearances:
        if KWappearances[pageID] == len(_queryIDs):
            relevantPages.append(pageID)

    # returns array of pageIDs for relevant pages
    return relevantPages

def normaliseRatings(ratings):
    # creates new dictionary without empty values
    formattedRatings = {key:val for key, val in ratings.items() if val != None}
    
    # calculates the standard deviation of the dataset
    if len(formattedRatings) != 0:
        mean = sum(formattedRatings.values())/len(formattedRatings)
        agg = 0
        for ratingID, rating in formattedRatings.items():
            agg += (rating - mean)**2
        stanDev = math.sqrt(agg / len(formattedRatings))
    
    else:
        # sets standard deviation to 0 if all values are none
        stanDev=0

    # uses standard deviations to calculate z-scores
    rankings = {}
    if stanDev!=0:
        for ratingID, rating in ratings.items():
            if rating!=None:
                z = (rating-mean)/stanDev
            else:
                # if the data provided is a none value it is given a z-score of 0
                z=0
            rankings[ratingID] = z
    else:
        # if the data has a standard deviation of 0 all z-scores are set to 0
        for ratingID, rating in ratings.items():
            rankings[ratingID] = 0

    # returns a dictionary of normalised values
    return rankings

def getRelRankings(_queryIDs, _relevantPages):
    relevancyRatings = []
    # gets the number of text types in use.
    textTypeIDs = formatSQL(cur.execute("select factorID from factorTbl where factorType=1").fetchall(), True)
    
    # NEEDS to be 0 initialised here, because a pageID that doesn't show under a specific textType must still have an entry
    for i in range(textTypeIDs[-1]):
        relevancyRatings.append({})
        for j in _relevantPages:
            relevancyRatings[i][j] = 0

    # pairs pageIDs and total TF-IDF rating for each text type.
    sqlQuery = 'select pageID, TFIDF, textTypeID from indexTbl where pageID in (%s) and wordID in (%s) and textTypeID in (%s)' % (",".join(map(str, _relevantPages)), ",".join(map(str, _queryIDs)), ",".join(map(str, textTypeIDs)))
    allTFIDFs = cur.execute(sqlQuery).fetchall()
    
    # increments tfIDFs across all words of query (keeps text types separate)
    for pageID, tfIDF, textTypeID in allTFIDFs:
        rating = relevancyRatings[textTypeID - 1]
        if pageID in rating:
            rating[pageID] += tfIDF

    # normalises the TF-IDF ratings (0.0 seconds)
    relevancyRankings = []
    for ratings in relevancyRatings:
        relevancyRankings.append(normaliseRatings(ratings))

    # returns normalised relevancy rankings
    return relevancyRankings

def getLocationRankings(_relevantPages, _userCC):
    # assigns each page a 1 or a 0 location rating
    locationRatings = {}
    pageCCs = formatSQL(cur.execute("select pageID, pageCC from pageTbl where pageID in ({})". format(",".join(map(str, _relevantPages)))).fetchall())
    for pageID, pageCC in pageCCs:
        # if in the same country as user assign a 1 rating
        if pageCC == _userCC:
            locationRatings[pageID]=1
        # assign a NONE rating if no location data is available
        elif pageCC == None:
            locationRatings[pageID]=None
        # assign a 0 value if page is in a different country
        else:
            locationRatings[pageID]=0

    # normalises the location ratings
    locationRankings = normaliseRatings(locationRatings)

    # returns normalised location ratings
    return locationRankings

def calcFinalPositions(_weightVals, _relevantPages, _relevancyRankings, _locationRankings):
    pageScores = {}
    pageIDscores = {}
 
    # finds out how many factors there are for each factor type.
    relevancyFactors = len(formatSQL(cur.execute("select factorID from factorTbl where factorType=1").fetchall(), True))
    pageFactors = formatSQL(cur.execute("select factorID from factorTbl where factorType=2").fetchall(), True)
    siteFactors = formatSQL(cur.execute("select factorID from factorTbl where factorType=4").fetchall(), True)

    # collects orders for factors
    orders = formatSQL(cur.execute("select factorOrder from factorTbl where factorOrder is not null").fetchall())

    # get all siteIDs in bulk
    # assumes that siteIDs are collected in same order than pageIDs are provided
    query = "select pageID, siteID from pageTbl where pageID in (%s)" % ','.join(str(x) for x in _relevantPages)
    pageSiteMatch = formatSQLdict(cur.execute(query).fetchall())
    siteIDs = pageSiteMatch.values()

    # get all page factor ratings in bulk
    query = "select normPageData from pageDataTbl where pageID in ({}) and pageFactorID in ({})".format(','.join(str(x) for x in _relevantPages), ",".join(map(str, pageFactors)))
    rawPageRatings = formatSQL(cur.execute(query).fetchall())

    query = "select siteID, normSiteData from siteDataTbl where siteID in ({}) and siteFactorID in ({})".format(','.join(str(x) for x in siteIDs), ",".join(map(str, siteFactors)))
    siteDataReturn = formatSQL(cur.execute(query).fetchall())

    # relies on data being collected in the correct order
    rawSiteRatings = {}
    for siteID, normSiteData in siteDataReturn:
        if siteID in rawSiteRatings:
            rawSiteRatings[siteID].append(normSiteData)
        else:
            rawSiteRatings[siteID] = [normSiteData]
    
    # multiplies every weight, order and rating for every factor on every page and sums the resultant number to develop an overall rating for every page.
    j = 0
    for pageID in _relevantPages:
        pageIDscores[pageID] = 0
        siteID = pageSiteMatch[pageID]
        scores = []

        i=0
        while i < relevancyFactors:
            rawRating = (_relevancyRankings[i])[pageID]
            scores.append(rawRating)
            pageIDscores[pageID] += rawRating * _weightVals[i]
            i+=1

        rawRating = _locationRankings[pageID]
        scores.append(rawRating)
        pageIDscores[pageID] += rawRating * _weightVals[relevancyFactors]

        i=0
        while i < len(pageFactors):
            rawPageRating = rawPageRatings[len(pageFactors)*j + i]
            scores.append(rawPageRating*orders[i])    
            pageIDscores[pageID] += rawPageRating * _weightVals[i+relevancyFactors+1]*orders[i]
            i+=1

        i=0
        while i < len(siteFactors):
            rawSiteRating = rawSiteRatings[siteID][i]
            scores.append(rawSiteRating*orders[i+len(pageFactors)])
            pageIDscores[pageID] += rawSiteRating*_weightVals[i+len(pageFactors)+relevancyFactors+1]*orders[i+len(pageFactors)]
            i+=1

        pageScores[pageID] = scores
        j+=1

 
    # sorts the search results in descending order of the rating.
    pageIDscoresList = sorted(pageIDscores.items(), key=lambda x:x[1], reverse=True)
    pageIDscores = dict(pageIDscoresList)
 
    # replaces the total rating in the dictionary with the individual rating for each factor.
    for pageID, rating in pageIDscores.items():
        pageIDscores[pageID] = pageScores[pageID]
   
    # returns pageIDs in descending score order each paired with a breakdown of their scores 
    return pageIDscores

def createResultsDict(pageIDscores, weights):
    resultsDict = []
    for pageID, scores in pageIDscores.items():
        #collects page's data to be displayed on results page
        siteID = formatSQL(cur.execute("select siteID from pageTbl where pageID=?",(pageID,)).fetchall())
        title = formatSQL(cur.execute("select pageTitle from pageTbl where pageID=?",(pageID,)).fetchall())
        description = formatSQL(cur.execute("select pageDescription from pageTbl where pageID=?",(pageID,)).fetchall())
        url = formatSQL(cur.execute("select pageURL from pageTbl where pageID=?",(pageID,)).fetchall()) #pageID vs domain
        favicon = formatSQL(cur.execute("select siteFavicon from siteTbl where siteID=?",(siteID,)).fetchall())
        domain = formatSQL(cur.execute("select siteDomain from siteTbl where siteID=?",(siteID,)).fetchall())

        # labels the page's score for each factor with the factor name
        formattedScores = {}
        i=0
        for factorName, weight in weights.items():
            formattedScores[factorName]=str(round(scores[i], 2))
            i+=1

        # creates the JSON for an individual result object and adds it to the list of results
        resultsDict.append({"details":{"title": title,"url": url,"domain": domain,"description": description,"favicon": favicon},"scores":formattedScores})
    return resultsDict

def search(query, weights, userCC):
    queryIDs = getWordIDs(query)
    if len(queryIDs)==0:
        return ""

    start = time.time()
    weightVals = getWeights(weights)
    end = time.time()
    print("get weights: "+str(end-start)+" seconds")

    start = time.time()
    relevantPages = selectRelPages(queryIDs)
    if len(relevantPages)==0:
        return ""
    end = time.time()
    print("get relevant pages: "+str(end-start)+" seconds")
    
    start = time.time()
    relevancyRankings = getRelRankings(queryIDs, relevantPages)
    end = time.time()
    print("relevancy rankings: "+str(end-start)+" seconds")
 
    start = time.time()
    locationRankings = getLocationRankings(relevantPages, userCC)
    end = time.time()
    print("location ranking: "+str(end-start)+" seconds")

    start = time.time()
    pageIDscores = calcFinalPositions(weightVals, relevantPages, relevancyRankings, locationRankings)
    end = time.time()
    print("calculate final positions: "+str(end-start)+" seconds")


    resultsDict = createResultsDict(pageIDscores, weights)

    return resultsDict

# connect to database on startup
conn = sqlite3.connect("shared_resources/database/SearchEngineIndex.db", check_same_thread=False)
cur = conn.cursor()

# POST request at URL/makeSearch
@app.route("/makeSearch", methods=["POST"])
def makeSearch():
    startTime = time.time()
    body = request.get_json()

    userCC = body["location"]
    weights = createWeightDict() # get from req eventually
    query = body["query"]
    autocorrect = body["autocorrect"] # get from req eventually

    if autocorrect == "1":
        correctedQuery = autocorrectQuery(query)
    else:
        correctedQuery=query

    # widgets add almost 2 secs of delay
    # try:
    #      widgetDict = getWidget(correctedQuery)
    # except:
    #      widgetDict=""
    widgetDict=""

    # try: 
    #     resultsDict = search(correctedQuery, weights, userCC)
    # except:
    #     resultsDict = ""

    resultsDict = search(correctedQuery, weights, userCC)

    if correctedQuery==query:
        correctedQuery=""

    
    outputDict = {
            "widget":widgetDict,
            "list": resultsDict,
            "correctedQuery": correctedQuery
    }

    outputJSON = json.dumps(outputDict)
    endTime = time.time()
    print("process time: "+str(endTime-startTime))

    return outputJSON

# GET request at URL/getFactors
@app.route("/getFactor")
def getFactors():
    conn = sqlite3.connect("shared_resources/database/SearchEngineIndex.db")
    cur = conn.cursor()

    ouputArray = []

    factorData = cur.execute("select factorName, factorDescription, factorType, defaultWeight from factorTbl").fetchall()
    for factorName, factorDescription, factorType, defaultWeight in factorData:
        if factorName == "Alt":
            factorName += " Text"
        if factorType == "1":
            factorName += " Relevancy"
        ouputArray.append({"factorName": factorName, "factorDescription": factorDescription, "defaultWeight": defaultWeight})
    
    outputJSON = json.dumps(ouputArray)
    return outputJSON