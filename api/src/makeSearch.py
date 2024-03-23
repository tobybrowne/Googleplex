
import sqlite3
import math
import json

import urllib
import sys

from bs4 import BeautifulSoup
import requests
import regex as re
import time
import wikipedia

import numpy as np

import os

from urllib.parse import urlparse
from urllib.parse import parse_qs



print("Content-type: application/json")
print("")

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
        
def autocorrectQuery(query):
    splitQuery = query.split(" ")
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

def getWeights(_weights):
    weightsArray = []
    for factorName, weight in _weights.items():
        weightsArray.append(float(weight))

    # returns an array containing just the weight values
    return weightsArray

def selectRelPages(_queryIDs):
    relevantPages = []
    KWappearances = {}
 
    for wordID in _queryIDs:
        # gets all the pages in which the word appears, removing repeats across the text types.
        kwPages = formatSQL(cur.execute("SELECT DISTINCT pageID FROM indexTbl WHERE wordID = ?", (wordID,)).fetchall(), True)

        #updates KWappearances with the pageID and how many of the query's keywords have appeared.
        for pageID in kwPages:
            if pageID in KWappearances:
                KWappearances[pageID]+=1
            else:
                KWappearances[pageID]=1

    # if the number of keyword appearances matches the number of keywords the site is deemed as relevant
    for pageID in KWappearances:
        if KWappearances[pageID] == len(_queryIDs):
            validPage = formatSQL(cur.execute("select valid from pageTbl where pageID=?", (pageID,)).fetchall())
            if validPage == 1:
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
    # pairs pageIDs and total TF-IDF rating for each text type.
    for i in textTypeIDs:
        rating = {}
        for pageID in _relevantPages:
            rating[pageID]=0
        for wordID in _queryIDs:
            sqlQuery = 'select pageID, TFIDF from indexTbl where pageID in (%s) and wordID=? and textTypeID=?' % ",".join(map(str, _relevantPages))
            allTFIDFs = formatSQL(cur.execute(sqlQuery, (wordID, i)).fetchall(), True)
            for pageID, tfIDF in allTFIDFs:
                # increments pageID value in rating with tf-idf
                if pageID in rating:
                    rating[pageID] += tfIDF

        relevancyRatings.append(rating)

 
    # normalises the TF-IDF ratings
    relevancyRankings = []
    for ratings in relevancyRatings:
        relevancyRankings.append(normaliseRatings(ratings))
    # returns normalised relevancy rankings
    return relevancyRankings

def getLocationRankings(_relevantPages, _userCC):
    # assigns each page a 1 or a 0 location rating
    locationRatings = {}
    for pageID in _relevantPages:
        pageCC = formatSQL(cur.execute("select pageCC from pageTbl where pageID=?", (pageID,)).fetchall())
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


    # multiplies every weight, order and rating for every factor on every page and sums the resultant number to develop an overall rating for every page.
    for pageID in _relevantPages:
        pageIDscores[pageID] = 0
        siteID = formatSQL(cur.execute("select siteID from pageTbl where pageID=?",(pageID,)).fetchall())
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



        query = "select normPageData from pageDataTbl where pageID=? and pageFactorID in (%s)" % ",".join(map(str, pageFactors))
        rawRatings = formatSQL(cur.execute(query, (pageID,)).fetchall())
        i=0
        while i < len(pageFactors):
            rawRating = rawRatings[i]
            scores.append(rawRating*orders[i])    
            pageIDscores[pageID] += rawRating * _weightVals[i+relevancyFactors+1]*orders[i]
            i+=1


        query = "select normSiteData from siteDataTbl where siteID=? and siteFactorID in (%s)" % ",".join(map(str, siteFactors))
        rawRatings = formatSQL(cur.execute(query, (siteID,)).fetchall())
        i=0
        while i < len(siteFactors):
            rawRating = rawRatings[i]
            scores.append(rawRating*orders[i+len(pageFactors)])
            pageIDscores[pageID] += rawRating*_weightVals[i+len(pageFactors)+relevancyFactors+1]*orders[i+len(pageFactors)]
            i+=1
        pageScores[pageID] = scores

 
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

    weightVals = getWeights(weights)


    relevantPages = selectRelPages(queryIDs)

    if len(relevantPages)==0:
        return ""
    relevancyRankings = getRelRankings(queryIDs, relevantPages)
 

    locationRankings = getLocationRankings(relevantPages, userCC)

    pageIDscores = calcFinalPositions(weightVals, relevantPages, relevancyRankings, locationRankings)


    resultsDict = createResultsDict(pageIDscores, weights)

    conn.close()

    return resultsDict

if __name__ == '__main__':
    testing = 1

    if testing == 0:
        conn = sqlite3.connect("D:\\webs\\www.tobybrowne.co.uk\\Googleplex\\api\\SearchEngineIndex.db")
        cur = conn.cursor()

        queryString = os.environ['QUERY_STRING']
        parsedQS = parse_qs(urlparse('http://www.tobybrowne.co.uk/fake.py?' + queryString).query)

        query = parsedQS["query"][0]
        userCC = parsedQS["location"][0]
        autocorrect = parsedQS["autocorrect"][0]
        parsedQS.pop("query")
        parsedQS.pop("location")
        parsedQS.pop("autocorrect")

        if len(parsedQS.items()) != 0:
            weights = {}
            for header, value in parsedQS.items():
                weights[header] = float(value[0])
        else:
            weights = createWeightDict()

    if testing == 1:
        conn = sqlite3.connect("shared_resources/database/SearchEngineIndex.db")
        cur = conn.cursor()

        query = "verstappen"
        autocorrect = 0
        userCC = "GB"

        simulatedUserWeights = [('Body Relevancy', ['0.55']), ('Header Relevancy', ['0.7']), ('Title Relevancy', ['1']), ('Alt Text Relevancy', ['0.38']), ('Description Relevancy', ['0.88']), ('Location', ['0.5']), ('Multimedia Frequency', ['0.23']), ('Page Speed', ['0.44']), ('SSL Encryption', ['1']), ('HTML Errors', ['0.2']), ('Word Count', ['0']), ('Reading Level', ['0.5']), ('Broken Links', ['0.4']), ('Date Published', ['0.8']), ('Text Contrast', ['0.6']), ('PageRank', ['0.7']), ('Domain Age', ['0.5']), ('Domain Registration Length', ['0.65']), ('Terms of Service Page', ['0.1']), ('Privacy Page', ['0.1'])]
        if len(simulatedUserWeights) != 0:
            weights = {}
            for header, value in simulatedUserWeights:
                weights[header] = float(value[0])
        else:
            weights = createWeightDict()
        
 

    if autocorrect == "1":
        correctedQuery = autocorrectQuery(query)
    else:
        correctedQuery=query

    try:
         widgetDict = getWidget(correctedQuery)
    except:
         widgetDict=""

    try: 
        resultsDict = search(correctedQuery, weights, userCC)
    except:
        resultsDict = ""

    if correctedQuery==query:
        correctedQuery=""

    
    outputDict = {
            "widget":widgetDict,
            "list": resultsDict,
            "correctedQuery": correctedQuery
    }

    outputJSON = json.dumps(outputDict)
    print(outputJSON)
        









    
