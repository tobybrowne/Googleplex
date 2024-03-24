query = "verstappen"
correctedQuery=query
autocorrect = 0
userCC = "GB"
widgetDict=""

simulatedUserWeights = [('Body Relevancy', ['0.55']), ('Header Relevancy', ['0.7']), ('Title Relevancy', ['1']), ('Alt Text Relevancy', ['0.38']), ('Description Relevancy', ['0.88']), ('Location', ['0.5']), ('Multimedia Frequency', ['0.23']), ('Page Speed', ['0.44']), ('SSL Encryption', ['1']), ('HTML Errors', ['0.2']), ('Word Count', ['0']), ('Reading Level', ['0.5']), ('Broken Links', ['0.4']), ('Date Published', ['0.8']), ('Text Contrast', ['0.6']), ('PageRank', ['0.7']), ('Domain Age', ['0.5']), ('Domain Registration Length', ['0.65']), ('Terms of Service Page', ['0.1']), ('Privacy Page', ['0.1'])]
if len(simulatedUserWeights) != 0:
    weights = {}
    for header, value in simulatedUserWeights:
        weights[header] = float(value[0])
else:
    weights = createWeightDict()