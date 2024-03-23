import json
import os
import sqlite3
import time
import urllib
from urllib.parse import parse_qs, urlparse

import regex as re
import requests
from bs4 import BeautifulSoup

import wikipedia
import wikipediaapi


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
 
def getFactors():
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




print("Content-type: application/json")
print("")

conn = sqlite3.connect("D:\\webs\\www.tobybrowne.co.uk\\Googleplex\\api\\SearchEngineIndex.db")
cur = conn.cursor()


print(getFactors())

    




