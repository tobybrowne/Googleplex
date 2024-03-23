import datetime
import json
import math
import re
import sqlite3
import time
import urllib.request
import warnings
from datetime import datetime, timezone
from urllib.parse import urlparse

import syllables
import tldextract
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import dateutil.parser
import enchant
import requests
from bs4 import BeautifulSoup, Comment
from requests.models import codes

processArray = []
browser = 0
errors = 0
nextQueue = []


# post-crawling functions
def updatePageRanks(iterationNum, d):
    pageIDs = formatSQL(cur.execute("select pageID from pageTbl where active=1").fetchall(), True) # collects active pageIDs
    factorID = formatSQL(cur.execute("select factorID from factorTbl where factorName=?", ("PageRank",)).fetchall()) # collects factorID for pageRank
    cur.execute("update pageDataTbl set rawPageData = 1 where pagefactorID=?", (factorID,)) # initialises all pageRank values on pageDataTbl
    y=0
    while y < iterationNum: # iterates calculations until "iterationNum" is reached
        for pageID in pageIDs:
            agg=0
            inLinks = formatSQL(cur.execute("select pageID from linkTbl where linkedPageID=?", (pageID,)).fetchall(), True) # collects page's inlinks
            for inLink in inLinks:
                pageRank = formatSQL(cur.execute("select rawPageData from pageDataTbl where pageFactorID=? and pageID=?", (factorID,inLink)).fetchall()) # finds page rank of inlink
                outlinkNum = len(formatSQL(cur.execute("select linkID from linkTbl where pageID = ?", (inLink,)).fetchall(), True)) # collects inlinks number of outlinks
                agg += pageRank/outlinkNum # calculates component of pageRank imparted
            cur.execute("update pageDataTbl set rawPageData = ? where pageFactorID = ? and pageID=?",((1-d)+(d*agg),factorID, pageID)) # updates pageID's pageRank value
        conn.commit()
        y+=1


def updateTFIDF():
    # collect number of pages and number of words
    numDocs = len(formatSQL(cur.execute("select pageID from pageTbl where active=1").fetchall(), True))
    numWords = formatSQL(cur.execute("select max(wordID) from wordTbl").fetchall())

    # iterates through words in wordTbl
    wordID = 1
    while wordID < numWords+1:
        # collects number of appearances for a given word
        wordApp = len(set(formatSQL(cur.execute("select pageID from indexTbl where wordID=?", (wordID,)).fetchall(), True)))
        if wordApp == 0: # in the event that a word has no appearances don't calculate idf value
            continue
        
        idf = math.log(int(numDocs)/int(wordApp)) # calculate idf value
        cur.execute("update indexTbl set TFIDF=termFreq*? where wordID = ?", (idf, wordID)) # update tf-idf values using new idf value
        wordID+=1

def normaliseRatings():
    siteFactors = formatSQL(cur.execute("select factorID from factorTbl where factorType=4").fetchall(), True)
    pageFactors = formatSQL(cur.execute("select factorID from factorTbl where factorType=2").fetchall(), True)

    cur.execute("update pageDataTbl set normPageData=0 where rawPageData is null")

    for factorID in pageFactors:
        mean = formatSQL(cur.execute("select avg(rawPageData) from pageDataTbl WHERE rawPageData is not null and pageFactorID = ?", (factorID,)).fetchall())

        if mean!=None:
            response = cur.execute("select SUM((rawPageData-?)*(rawPageData-?)), count(*) from pageDataTbl where pageFactorID=? and rawPageData is not null", (mean, mean, factorID)).fetchall()[0]
            agg = response[0]
            count = response[1]
            stanDev = math.sqrt(agg/count)
            if stanDev == 0:
                cur.execute("UPDATE pageDataTbl SET normPageData=0 WHERE pageFactorID=?", (factorID,))
            else:
                cur.execute("UPDATE pageDataTbl SET normPageData=(rawPageData-?)/? WHERE pageFactorID=? and rawPageData is not null", (mean, stanDev, factorID))


    cur.execute("update siteDataTbl set normSiteData=0 where rawSiteData is null")
    for factorID in siteFactors:
        mean = formatSQL(cur.execute("select avg(rawSiteData) from siteDataTbl WHERE rawSiteData is not null and siteFactorID = ?", (factorID,)).fetchall())
        if mean!=None:
            response = cur.execute("select SUM((rawSiteData-?)*(rawSiteData-?)), count(*) from siteDataTbl where siteFactorID=? and rawSiteData is not null", (mean, mean, factorID)).fetchall()[0]
            agg = response[0]
            count = response[1]
            stanDev = math.sqrt(agg/count)
            if stanDev == 0:
                cur.execute("UPDATE siteDataTbl SET normSiteData=0 WHERE siteFactorID=?", (factorID,))
            else:
                cur.execute("UPDATE siteDataTbl SET normSiteData=(rawSiteData-?)/? WHERE siteFactorID=? and rawSiteData is not null", (mean, stanDev, factorID))


# other crawling processes
def indexPage(_pageText, _pageID):
    # iterates through every text type
    for textTypeName, text in _pageText.items():
        textTypeID = formatSQL(cur.execute("select factorID from factorTbl where factorName=?", (textTypeName,)).fetchall())
        #textTypeID = formatSQL(cur.execute("select textTypeID from textTypeTbl where textTypeName=?", (textTypeName,)).fetchall())
        length = len(text)
        frequencies = {}

        # converts the text into a dictionary of word:frequency pairs
        for word in text:
            if word in frequencies:
                frequencies[word]+=1
            else:
                frequencies[word]=1

        for word, frequency in frequencies.items():
            # attempts to collect wordID for given word
            wordID = formatSQL(cur.execute("select wordID from wordTbl where word=?", (word,)).fetchall())
            
            # creates wordTbl record for word if doesn't exist
            if wordID == None:
                cur.execute("insert into wordTbl (word) values (?)", (word,))
                wordID = formatSQL(cur.execute("select last_insert_rowid()").fetchall())
        
            # calculates TF value and updates indexTbl
            tf = frequency/length
            cur.execute("insert into indexTbl (wordID, pageID, termFreq, textTypeID) values (?, ?, ?, ?)", (wordID, _pageID, tf, textTypeID))

def addLinksToDB(_links, _pageID):
    global nextQueue

    for link in _links:
        linkedPageID = formatSQL(cur.execute("select pageID from pageTbl where pageURL=?", (link,)).fetchall()) # attempts to collect pageID for linked page
        if linkedPageID == None: # if page not in pageTbl
            cur.execute("insert into pageTbl (pageURL, active, valid) values(?, 0, 1)", (link,)) # creates a "stub" record for the linked page
            linkedPageID = formatSQL(cur.execute("select last_insert_rowid()").fetchall()) # collects ID for "stub" record
            
            if link not in nextQueue: # adds to queue if not already in it
                nextQueue.append(link)
        # creates a linkTbl record
        cur.execute("insert into linkTbl (pageID, linkedPageID) values(?,?)", (_pageID, linkedPageID))

def addPageTypeToDB(_pageType, _siteID, _pageText):
    # finds factorID for given page type factor
    factorID = formatSQL(cur.execute("select factorID from factorTbl where factorName=?", (_pageType,)).fetchall())

    # finds current rating for given page type
    pageTypeRecord = formatSQL(cur.execute("select siteDataID from siteDataTbl where siteFactorID=? and siteID=?", (factorID, _siteID)).fetchall())

    pageResult = isPage(_pageText, _pageType) # finds if current page is the given page type

    if pageTypeRecord==None: # creates a siteDataTbl record if it doesnt exist
        cur.execute("insert into siteDataTbl (siteID, siteFactorID, rawSiteData) values (?,?,?)", (_siteID, factorID, pageResult))
    else: # updates siteDataTbl if the rating has changed from 0 to 1
        if pageTypeRecord==0 and pageResult==1:  
            cur.execute("update siteDataTbl set rawSiteData=1 where siteID=? and siteFactorID=?", (_siteID, factorID))

def waitLoad(driver):
    timing = []
    fullLengths = []
    i=0
    oldLength = 0
    flag = 0
    start = time.time()
    while True:
        if flag == 150:
            break
        length = len(driver.page_source)
        timing.append(i)
        fullLengths.append(length)
        if length == oldLength:
            flag+=1
        else:
            flag = 0
        oldLength = length
        time.sleep(0.1)
        i+=1
    end = time.time()
    return end-start


# ranking factors

def isPage(_pageText, _pageType):
    if _pageType == "Privacy Page":
        for textType, text in _pageText.items():
            if textType == "Title" or textType == "Header" or textType == "Description": # only searches for text in the title, header or description
                textString = " ".join(text) # forms a string containing all the text
                if "privacy policy" in textString or "privacy statement" in textString: # searches for key terms
                    return 1
        return 0

    elif _pageType == "Terms of Service Page":
        for textType, text in _pageText.items():
            if textType == "Title" or textType == "Header" or textType == "Description": # only searches for text in the title, header or description
                textString = " ".join(text) # forms a string containing all the text
                if "terms of service" in textString or "terms and conditions" in textString or "terms conditions" in textString: # searches for key terms
                    return 1
        return 0 

def getDomainAge(_domain):
    # queries API
    url = "https://api.promptapi.com/whois/query?domain="+urllib.parse.quote(_domain)
    headers= {"apikey": "meZNGfQCbNGXdnY7IbCR22XwkLp5fTXq"}
    response = requests.request("GET", url, headers=headers)
    
    # parses API response
    responseJSON = json.loads(response.text)
    creationDate = responseJSON["result"]["creation_date"].split(" ")[0]
    expirationDate = responseJSON["result"]["expiration_date"].split(" ")[0]
    updatedDate = responseJSON["result"]["updated_date"].split(" ")[0]

    # calculates final rating
    regLength = datetime.strptime(expirationDate, '%Y-%m-%d') - datetime.strptime(updatedDate, '%Y-%m-%d')
    unixCreationDate = (datetime.strptime(creationDate, '%Y-%m-%d') - datetime(1970, 1, 1)).total_seconds()

    return regLength.days, unixCreationDate

def getMultimediaFrequency(driver):
    images = len(driver.find_elements_by_tag_name('img')) # collects number of images on page
    video = len(driver.find_elements_by_tag_name('video')) # collects number of images on page
    return images + video # returns total number of multimedia elements

def getSSL(_url):
    # gets protocol from URL
    splitURL = _url.split(":")
    protocol = splitURL[0]

    if protocol=="https": # if protocol is https return 1
        return 1
    else:
        # replaces http with https in url
        splitURL[0] = "https"
        newURL = ":".join(splitURL)

        # if new https url is valid return 1, else return 0
        if isValidURL(newURL)==True:
            return 1
        else:
            return 0

def getHTMLErrors(_url):
    # requests data from API
    apiRequest = "https://validator.w3.org/nu/?doc="+_url+"&out=json"
    response = requests.get(apiRequest)
    
    # parses output
    responseJSON = json.loads(response.text)
    messages = responseJSON["messages"]

    # counts errors in response
    errors = 0
    for message in messages:
        if message["type"]=="error":
            errors+=1

    # returns error count
    return errors

def getWordCount(_bodySplit):
    return len(_bodySplit)

def linkCalcs(driver):
    links = driver.find_elements_by_tag_name('a') # collects link elements
    totalLinks = len(links) # finds total number of link elements

    if totalLinks == 0: # if no links found return 0, []
        return None, []

    workingLinks = []
    brokenLinks = 0

    for link in links:
        url = link.get_attribute("href") # collect link url

        # adds url to "workingLinks" if it exists in database
        response = formatSQL(cur.execute("select pageID from pageTbl where pageURL=?", (url,)).fetchall())
        if response != None:
            workingLinks.append(url)
            continue

        # if url is valid add to "workingLinks", otherwise increment "brokenLinks"
        if isValidURL(url) == True:
            workingLinks.append(url)
        else:
            brokenLinks+=1

    brokenLinkRating = brokenLinks/totalLinks # calculates proportion of broken links
    return brokenLinkRating, workingLinks

def isValidURL(_url):
    try: # tries to query url
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36', "Upgrade-Insecure-Requests": "1","DNT": "1","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": "en-US,en;q=0.5","Accept-Encoding": "gzip, deflate"} # http headers
        status = requests.get(_url, headers=headers).status_code # query url and collect status
        if status == 404: # if 404 error is returned then return false
            return False
        else:
            return True # if url is successfully queried return true
    except: # if url can't be reached return false
        return False


def getDateTimePublished(driver):
    try: # tries to find datetime data in meta tags
        found = False 
        metaTags = driver.find_elements_by_tag_name('meta')
        for metaTag in metaTags:
            if metaTag.get_attribute("property") == "article:published_time":
                dateTime = metaTag.get_attribute("content")
                found=True
        if found == False:
            raise ValueError('no time tag found') # raises an error, exiting the try-except statement 
 
    except: # if no datetime meta tags found search for <time> tags
        try:
            timeTag = driver.find_element_by_tag_name('time')
            dateTime = timeTag.get_attribute("datetime")
        except:
            dateTime = None


    # if a datetime value is extracted from either methods:
    if dateTime != None:
        # tries to format the datetime data, otherwise sets datetime to None
        try:
            dateTime = dateutil.parser.isoparse(dateTime)

            # if no timezone is provided, set it to UTC
            if dateTime.tzinfo==None:
                dateTime = dateTime.replace(tzinfo=timezone.utc)

            # convert time to UNIX timestamp
            dateTime = (dateTime - datetime.datetime(1970, 1, 1).replace(tzinfo=timezone.utc)).total_seconds()
        except:
            dateTime = None
    
    return dateTime

def getTextContrast(driver):
    textElements = driver.find_elements_by_tag_name('p') # find all "p" tags
    totalCharacterCount = 0
    agg=0

    # if no text elements return None
    if len(textElements)==0:
        return None
 
 
    for element in textElements:
        characterCount = len(element.text)

        # if the page text element has no text go to the next text element
        if characterCount == 0:
            continue

        # increments character count
        totalCharacterCount += characterCount
 
	   # gets text RGB value
        textRGB = element.value_of_css_property('color')[5:-1].split(",")[0:3]
        textRGB = [int(item) for item in textRGB]
        
        # gets background RGB value
        found = False
        depth = 0
        while found == False:
            try:
                if depth != 0:
                    element = element.find_element_by_xpath('..') 
               
                bgRGB = element.value_of_css_property('background-color')[5:-1].split(",")
 
                opacity = bgRGB[-1]
                if opcaity != 0:
                    found = True
            except:
                bgRGB = [255, 255, 255, 1]
                found=True
            depth+=1
 
        bgRGB = bgRGB[0:3]
        allRGBvalues = textRGB+bgRGB
 
	    # converts sRGB values to linear RGB values
        i=0
        for c in allRGBvalues:
            c = c/255
            if c > 0.03928:
                allRGBvalues[i] = ((c+0.055)/1.055)**2.4
            else:
                allRGBvalues[i] = c/12.92
           
            i+=1
 
	    # calculates luminance values
        textLum = (0.2126*allRGBvalues[0])+(0.7152*allRGBvalues[1])+(0.0722*allRGBvalues[2])
        bgLum= (0.2126*allRGBvalues[3])+(0.7152*allRGBvalues[4])+(0.0722*allRGBvalues[5])
 
	    # calculates contrast ratings from luminance values
        if textLum > bgLum:
            contrastRating = (textLum+0.05/bgLum+0.05)
        else:
            contrastRating = (bgLum+0.05)/(textLum+0.05)
 
        agg += contrastRating*characterCount
 
    # returns none if all text elements are empty
    if totalCharacterCount == 0:
        return None

    # returns average text
    return agg/totalCharacterCount

def getReadLevel(_body):
    # divides the body text into an array of sentences
    sentenceList = re.split(r"[.?!]\s*",_body)
    sentenceList[:] = [x for x in sentenceList if x!=""]
    
    sentenceCount = len(sentenceList)

    # divides the body text into an array of words
    wordString = " ".join(sentenceList)
    wordFormatted = re.sub(r"[^a-zA-Z\s]", "", wordString) 
    wordList = wordFormatted.split(" ")
    wordList[:] = [x for x in wordList if x!=""]
    wordCount = len(wordList)

    # returns a word count of 0 if there are no words.
    if wordCount==0:
        return None

    # counts total number of syllables in sampled text
    totalSyllables = 0
    for word in wordList:
        numSyllables = syllables.estimate(word)
        totalSyllables += numSyllables
        
    # calculates reading level
    readingLevel = 206.835 - 1.015*(wordCount/sentenceCount) - 84.6*(totalSyllables/wordCount)
    return readingLevel



def getElementText(elements):
    # iterates through elements appending each ones text to a string
    text = ""
    i=0
    for element in elements:
        newText = " "+element.text
        text += newText
        i+=1

    # returns single string
    return text
def splitRemovePunc(text):
    formattedText = ""

    # remove any characters that aren't alphanumeric or spaces
    for character in text:
        if character.isalnum()==True or character == " ":
            formattedText+=character
    
    # divides text into array of words and removes empty elements.
    formattedText = formattedText.split(" ") 
    formattedText[:] = [x for x in formattedText if x!=""]

    return formattedText
def getPageText(driver):
    # collects header and title text
    headerSplit = splitRemovePunc(getElementText(driver.find_elements_by_tag_name('h1')).lower())
    titleSplit = splitRemovePunc(driver.title.lower())

    # collects body text
    bodyText = getElementText(driver.find_elements_by_tag_name('p'))
    bodySplit = splitRemovePunc(bodyText.lower())
   
   # collects alt text
    images = driver.find_elements_by_tag_name('img')
    altSplit = []
    for image in images:
        newAltText = image.get_attribute("alt")
        altSplit += splitRemovePunc(newAltText.lower())
 
    # collects meta description
    metaTags = driver.find_elements_by_tag_name('meta')
    descriptionSplit = []
    descriptionText = ""
    for metaTag in metaTags:
        if metaTag.get_attribute("name") == "Description" or metaTag.get_attribute("name") == "description":
            descriptionText = metaTag.get_attribute("content")
            descriptionSplit = splitRemovePunc(descriptionText.lower())

 
    # compiles text into dictionary of page text
    pageTextSplit = {"Body":bodySplit, "Header":headerSplit, "Title":titleSplit, "Alt":altSplit, "Description":descriptionSplit}
    
    return pageTextSplit, bodyText

# returns page's country code
def getLocation(driver, _domain): 
    tld = _domain.split(".")[-1].upper() # extracts tld from domain
    # if tld is UK return GB
    if tld == "UK":
        return "GB"
    # returns tld if it exists in "countryCode.json"
    else:
        countryCodes = json.load(open("..//resources//countryCodes.json"))
        for country in countryCodes:
            if country["Code"] == tld:
                return tld

    # if language code includes a country code then return it
    langCode = driver.find_element_by_tag_name("html").get_attribute("lang")
    if len(langCode)>2:
        countryCode = langCode[-2:]
        return countryCode.upper()



# framework functions
def crawlSites(queue, maxDepth, updating):
    global nextQueue
    global processArray

    # generates error log file name
    timestamp = datetime.today().strftime("%Y-%m-%d [%H'%M'%S]")
    fileName = "..//..//resources//logs//"+timestamp+".txt"
            
    # initialise browser  
    browser = initialiseDriver(True)
    print("SUCCESSFULLY LOADED WEB BROWSER!")

    nextQueue = []
    depth = 0
    pagesCrawled = 0
    errors = 0

    while depth <= maxDepth: 
        for url in queue:

            # starts measuring time taken for page to be crawled
            pageStartTime = time.time()

            logObject = {}
            processArray = []
            logObject["url"]=url

            print("==================================================================================")
            print(url)
            print("==================================================================================")

            # finds page domain
            decomposedURL = tldextract.extract(url)
            domain = decomposedURL.domain+"."+decomposedURL.suffix


            if updating == True:
                # sets pageID to None so page data is re-collected
                pageID = None
            else:
                # attempts to find pageID
                pageID = formatSQL(cur.execute("select pageID from pageTbl where pageURL=?", (url,)).fetchall())
             
            # if page has a record...
            if pageID != None:
                active = formatSQL(cur.execute("select active from pageTbl where pageURL=?", (url,)).fetchall())
                valid = formatSQL(cur.execute("select valid from pageTbl where pageURL=?", (url,)).fetchall())
                if active==0 and valid == 1:
                    siteID = formatSQL(cur.execute("select siteID from siteTbl where siteDomain=?", (domain,)).fetchall())
                    cur.execute("update pageTbl set siteID=? where pageID=?", (siteID, pageID))
                else:
                    continue
   
            else:
                if updating == True:
                    siteID = None # sets siteID to None so site data is re-collectd
                    pageID = formatSQL(cur.execute("select pageID from pageTbl where pageURL=?", (url,)).fetchall()) # collects pageID from pageTbl
                else:
                    # attempts to find siteID and updates page record with collected value
                    siteID = formatSQL(cur.execute("select siteID from siteTbl where siteDomain=?", (domain,)).fetchall())
                    cur.execute("insert into pageTbl (pageURL, siteID) values(?,?)", (url, siteID))
                    
                    # gets pageID of recently created pageTbl record
                    pageID = formatSQL(cur.execute("select last_insert_rowid()").fetchall())
           
            # if site isn't crawled...
            if siteID == None:
                if updating == True:
                    siteID = formatSQL(cur.execute("select siteID from siteTbl where siteDomain=?", (domain,)).fetchall())  # collects siteID
                else:
                    # creates siteTbl record and collects it's siteID
                    cur.execute("insert into siteTbl (siteDomain) values(?)", (domain,))
                    siteID = formatSQL(cur.execute("select last_insert_rowid()").fetchall())
                    
                    # updates pageTbl record with siteID
                    cur.execute("update pageTbl set siteID=? where pageID=?", (siteID, pageID))                    


                siteRatings = {}

                # calculates domain age rating and domain registration length
                domainAgeRating, domainRegLengthRating = doProcess(lambda: getDomainAge(domain), "DOMAIN CALCULATIONS", (None, None))
                siteRatings["Domain Age"] = domainAgeRating
                siteRatings["Domain Registration Length"] = domainRegLengthRating

                # adds site ratings to database
                records = []
                for factorName, rating in siteRatings.items():
                    factorID = formatSQL(cur.execute("select factorID from factorTbl where factorName=?", (factorName,)).fetchall())
                    records.append((rating, siteID, factorID))

                if updating == True:
                    for record in records:
                        cur.execute("update siteDataTbl set rawSiteData=? where siteID=? and siteFactorID=?", record)
                else:
                    cur.executemany("insert into siteDataTbl (rawSiteData, siteID, siteFactorID) values(?,?,?)", records) # changed order

                print("====================== ADDED SITE DATA ======================")

                # tries to collect favicon URL
                faviconURL = "/".join(url.split("/")[0:3])+"/favicon.ico"
                if isValidURL(faviconURL)==True:
                    cur.execute("update siteTbl set siteFavicon=? where siteID=?", (faviconURL, siteID))

            pageRatings = {}

            # gets page in selenium browser
            response = doProcess(lambda: browser.get(url), "LOADING PAGE", "fail")
            # skips to next page if the process fails
            if response == "fail":
                pageEndTime = time.time()
                addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                continue

            # collecting page speed rating / wait to load
            pageSpeedRating = doProcess(lambda: waitLoad(browser), "WAITING FOR LOADING TO FINISH [PAGE SPEED RATING]")
            # skips to next page if the process fails
            if pageSpeedRating == None:
                pageEndTime = time.time()
                addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                continue
            pageRatings["Page Speed"] = pageSpeedRating

            # collects page text
            pageTextOutput = doProcess(lambda: getPageText(browser), "COLLECTING PAGE TEXT", (None, None, None)) # hola
            # skips to next page if the process fails
            if pageTextOutput == "fail":
                pageEndTime = time.time()
                addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                continue

            pageText, body = pageTextOutput

            # clears indexTbl records before updating a page
            if updating == True:
                cur.execute("delete from indexTbl where pageID=?", (pageID,))

            # indexes page
            response = doProcess(lambda: indexPage(pageText, pageID), "INDEXING PAGE", "fail") # hola
            # exits program is process fails
            if response=="fail":
                pageEndTime = time.time()
                addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                exit()

            





            # calculates multimedia frequency
            multimediaFreqRating = doProcess(lambda: getMultimediaFrequency(browser), "CALCULATING MULTIMEDIA FREQUENCY")
            pageRatings["Multimedia Frequency"] = multimediaFreqRating


            # calculates SSL rating
            sslRating = doProcess(lambda: getSSL(url), "CALCULATING SSL RATING")
            pageRatings["SSL Encryption"] = sslRating

            # calculates HTML error rating
            htmlErrorRating = doProcess(lambda: getHTMLErrors(url), "CALCULATING HTML ERROR RATING")
            pageRatings["HTML Errors"] = htmlErrorRating

            # calculates word count rating
            wordCountRating = doProcess(lambda: getWordCount(body), "CALCULATING WORD COUNT RATING")
            pageRatings["Word Count"] = wordCountRating

            # calculates reading level
            readLevelRating = doProcess(lambda: getReadLevel(body), "CALCULATING READING LEVEL RATING")
            pageRatings["Reading Level"] = readLevelRating

            # collects page links and calculates broken link rating
            brokenLinkRating, links = doProcess(lambda: linkCalcs(browser), "LINK CALCULATIONS", (None, []))
            pageRatings["Broken Links"] = brokenLinkRating


            # clears linkTbl records before updating a page
            if updating == True:
                cur.execute("delete from linkTbl where pageID=?", (pageID,))
            
            # populates linkTbl
            response = doProcess(lambda: addLinksToDB(links, pageID), "ADDING LINKS TO DATABASE", "fail")
            # exits program is process fails
            if response=="fail":
                pageEndTime = time.time()
                addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                exit()


            # finds date published
            dateTimeRating = doProcess(lambda: getDateTimePublished(browser), "CALCULATING DATE PUBLISHED RATING")
            pageRatings["Date Published"] = dateTimeRating

            # calculates text contrast rating
            textContrastRating = doProcess(lambda: getTextContrast(browser), "CALCULATING TEXT CONTRAST RATING")
            pageRatings["Text Contrast"] = textContrastRating

            # initialises pageRank value
            pageRatings["PageRank"] = None
            
            # adds page ratings to database
            records = []
            for factorName, rating in pageRatings.items():
                factorID = formatSQL(cur.execute("select factorID from factorTbl where factorName=?", (factorName,)).fetchall())
                records.append((rating, pageID, factorID))
            if updating == True:
                for record in records:
                    cur.execute("update pageDataTbl set rawPageData=? where pageID=? and pageFactorID=?", record)
            else:
                cur.executemany("insert into pageDataTbl (rawPageData, pageID, pageFactorID) values(?,?,?)", records) # changed order

            # process for updating page type records
            pageTypes = ["Terms of Service Page", "Privacy Page"]
            for pageType in pageTypes:
                response = doProcess(lambda: addPageTypeToDB(pageType, siteID, pageText), pageType+" IDENTIFICATION", "fail")
                # exits program if process fails
                if response=="fail":
                    pageEndTime = time.time()
                    addToLog("failure", pageEndTime-pageStartTime, processArray, url, fileName)
                    exit()

            # finds page location 
            location = doProcess(lambda: getLocation(browser, domain), "GET LOCATION")
            cur.execute("update pageTbl set pageCC=? where pageID=?", (location, pageID)) 


            title = browser.title # collects page title
            
            # collects page description
            description = " ".join(pageText["Description"])[0:220]
            if description == "":
                description = body[0:220]
            description+="..."

            # gets timestamp for the time page was crawled
            currentTimestamp = (datetime.now().replace(tzinfo=timezone.utc) - datetime(1970, 1, 1).replace(tzinfo=timezone.utc)).total_seconds()

            # updates pageTbl
            cur.execute("update pageTbl set pageTitle=?, pageDescription=?, dateCrawled=?, active=1, valid=1 where pageID=?", (title, description, currentTimestamp, pageID))

            conn.commit()

            pageEndTime = time.time() # stops page crawl time timer



            addToLog("success", pageEndTime-pageStartTime, processArray, url, fileName) # adds data to error log

        queue = nextQueue # swaps to next layer of pages to crawl
        depth+=1

    browser.quit() # closes driver

    print("==================================================================================\n")
    print("                                   FINISHED!                                      ")
    print("==================================================================================\n")

def getDiscoveredPages():
    return formatSQL(cur.execute("select pageURL from pageTbl where active=0 and valid=1").fetchall())

def addToLog(status, timeDelta, _processArray, _url, _fileName):
    logObject = {}
    logObject["url"]=_url
    logObject["status"] = status
    logObject["time"] = timeDelta
    logObject["processes"]=_processArray
    logObjectJSON = json.dumps(logObject)
    f = open(_fileName, "a")
    f.write(logObjectJSON+",")
    f.close() 

def doProcess(process, processName, failureResult=None, criticalProcess=False):
    global processArray
    global errors

    print(processName+"...") # displays the process being executed
    start=time.time() # starts timing the process
    message = "success"


    try:
        output = process()     # attempts to run the function
    except Exception as e:
        output = failureResult # if the function fails the output is either None or a pre-defined output
        message = str(e) # collects the error message
        print(message)
        errors+=1

    end=time.time() # ends the timer.
    processArray.append({"processName": processName, "Message": message, "Time": str(end-start)}) # creates the process log object

    print("DONE!\n")
    print("==================================================================================")

    return output    

def initialiseDriver(headless):
    chrome_options = Options()
    if headless == True:
        chrome_options.add_argument("--headless")   
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    warnings.filterwarnings("ignore", category=DeprecationWarning)                                                                          
                                                               
    return webdriver.Chrome(ChromeDriverManager(version="100.0.4896.60").install(), options=chrome_options)

def connectDB():
    conn = sqlite3.connect("..//..//resources//database//SearchEngineIndex.db")
    cur = conn.cursor()
    return conn, cur

def getInvalidPageIDs():
    invalidPageIDs = []
    activePages = formatSQL(cur.execute("select pageID, pageURL from pageTbl where active=1").fetchall()) # collects active pages
    
    # iterates through active urls and finds invalid ones
    for pageID, url in activePages:
        if isValidURL(url)==False: 
            invalidPageIDs.append(pageID)
    
    return invalidPageIDs
def markInvalidPages(invalidPageIDs):
    for pageID in invalidPageIDs:
        cur.execute("update pageTbl set valid=0, active=0 where pageID=?", (pageID,))

def getURLsToUpdate(_ageForUpdate):
    URLsToUpdate = []
    activePages = formatSQL(cur.execute("select pageURL, dateCrawled from pageTbl where active=1").fetchall(), True) # collects active pages
    currentTimestamp = (datetime.now() - datetime(1970, 1, 1)).total_seconds() # gets current timestamp
    y=0

    # finds records older than the age inputted
    for url, dateCrawled in activePages:
        if (currentTimestamp - dateCrawled) > _ageForUpdate:
            URLsToUpdate.append(url)

    return URLsToUpdate

def clearDatabase():
    cur.execute("delete from indexTbl")
    cur.execute("delete from linkTbl")
    cur.execute("delete from pageDataTbl")
    cur.execute("delete from pageTbl")
    cur.execute("delete from siteDataTbl")
    cur.execute("delete from siteTbl")
    cur.execute("delete from wordTbl")
    #cur.execute("delete from siteFactorTbl")
    #cur.execute("delete from pageFactorTbl")

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


print("  _____    _         _     __      __   _       ___                 _               ")       
print(" |_   _|__| |__ _  _( )___ \ \    / /__| |__   / __|_ _ __ ___ __ _| |___ _ _ ___   ")
print("   | |/ _ \ '_ \ || |/(_-<  \ \/\/ / -_) '_ \ | (__| '_/ _` \ V  V / / -_) '_(_-<   ")
print("   |_|\___/_.__/\_, | /__/   \_/\_/\___|_.__/  \___|_| \__,_|\_/\_/|_\___|_| /__/   ")
print("                |__/                                                             \n ")                                                          

conn, cur = connectDB()



nextQueue = []
processArray = []

print("================== CONNECTED TO DATABASE ==================")

while True:
    # main start message
    print("WHAT WOULD YOU LIKE TO DO? [CRAWL / RANK / GET STATS / CLEAR / UPDATE / QUIT]")
    response = input()

    if response == "1":
        queue = []
        while True:
            print("HOW WOULD YOU LIKE TO CRAWL? [ENTER SEED URLS / CONTINUE FROM DISCOVERED PAGES / EXIT]")
            response = input()

            if response == "1":
                # asks user for seed urls until "f" is pressed
                while True:
                    seedURL = input("INPUT SEED URL ['F' TO FINISH]: ")
                    if seedURL.lower() == "f":
                        break
                    if isValidURL(seedURL)==True:
                        queue.append(seedURL)
                        print("VALID URL")
                    else:
                        print("INVALID URL")
                break

            elif response == "2":
                # collects stub pages
                queue = getDiscoveredPages()
                print(len(queue))

                # if no pages found ask for another method of inputting pages
                if len(queue)==0:
                    print("NO VALID PAGES FOUND!")
                else:
                    break
            
            # exits process to return to start
            elif response == "3":
                break

            else:
                print("INVALID INPUT!")

        # if this process is exited with an empty queue return to start
        if len(queue) == 0:
            print("NO VALID URLS ADDED")
            continue

        print(str(len(queue))+" SEED URL(S) QUEUED") 

        # prompts user for traversal depth until a valid value is provided or "e" is input
        leave = False
        while True:
            depth = input("ENTER TRAVERSAL DEPTH ['E' TO EXIT]: ")
            if depth.isdigit()==True: 
                depth = int(depth)
                break
            elif depth.lower() == "e":
                leave = True
                break
            print("INVALID TRAVERSAL DEPTH!")

        # returns to start
        if leave == True:
            continue

        # prompts user before starting crawling
        print("PRESS ANY KEY TO START CRAWLING")
        input()
        crawlSites(queue, depth, False)
                   
    elif response == "2":
        # normalised ratings
        print("NORMALISING RATING DATA...")
        normaliseRatings()

        # updated tf-idf values
        print("UPDATING TF-IDF VALUES...")
        updateTFIDF()

        # update page ranks
        print("UPDATING PAGE RANK DATA...")
        updatePageRanks(3, 0.15)
        
        conn.commit()

    elif response == "3":
        activePages = len(formatSQL(cur.execute("select pageID from pageTbl where active=1").fetchall(), True)) # collects active pages
        activeSites = len(formatSQL(cur.execute("select siteID from siteTbl").fetchall(), True)) # collects sites
        words = len(formatSQL(cur.execute("select wordID from wordTbl").fetchall(), True)) # collects all indexed words
        
        # outputs key stats
        print("ACTIVE PAGES: "+str(activePages))
        print("ACTIVE SITES: "+str(activeSites))
        print("WORDS: "+str(words))
        input()

    elif response == "4":
        # clears database
        clearDatabase()
        conn.commit()
        print("DATABASE CLEARED")
        input()

    elif response == "5":
        while True:
            queue=[]
            ageForUpdate = input("INPUT REQUIRED RECORD AGE FOR UPDATING ['E' TO EXIT]: ")

            # returns to start message if input is "e"
            if ageForUpdate.lower()=="e":
                break

            # collected records older than age inputted
            queue = getURLsToUpdate(int(ageForUpdate))
            numURLs = len(queue)

            if numURLs == 0:
                # loop continues until the updating process is exited or an age that returns valid URLs is entered
                print("NO URLS TO UPDATE")
            else:
                break
        
        # returns to home page if process exited with no URLs in queue
        if len(queue)==0:
            continue

        while True:
            # prompts user before updating
            print("UPDATE "+str(numURLs)+" URLs? [Y/N]")
            response = input()
            if response.lower() == "y":
                crawlSites(queue, 0, True)
            elif response.lower() == "n":
                break
            else:
                print("INVALID INPUT")

    elif response == "6":
        # exits process
        print("QUITTING")
        exit()
    
    else:
        print("INVALID INPUT!")


                



