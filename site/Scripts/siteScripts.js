function goBack(){
    var urlParams = new URLSearchParams(window.location.search); // collects query strings
    var page = urlParams.get('page'); // extracts "page" value from query strings

    //sends user to home page if no page query string found
    if(page!="Home" && page!="Results"){
        location.href = "HomePage.html?page=Settings";
    }
    // otherwise sends the user to the page they originated from
    else{
        location.href = page+"Page.html?page=Settings";
    }

}

function openSettingsPage(page){
    location.href = "SearchSettingsPage.html?page="+page;
}

function loadSettingsPage(){
    var total = factorData.length;

    // Displays all results.    
    for(var i=0; i < total; i++){
        factorName = factorData[i]["factorName"];
        factorDescription = factorData[i]["factorDescription"];
        $("#container").append(`<div class="factorContainer">
                                        <div class="factorControls">
                                            <p class="settingsPage factorTitle" id="Header`+i+`">`+factorName+`</p>
                                            <div class="settingsPage" id="sliderWrapper">
                                                <input type="range"  min="-1" max="1" step="0.01" value="0" class="settingsPage slider" name="`+i+`" oninput="sliderInput(this.name, this.value)" id="slider`+i+`">
                                            </div>
                                            <input type="number" oninput="entryInput(this.name, this.value)" value="1" step="0.01" class="settingsPage weightInp" name="`+i+`" id="NumInp`+i+`" min="-1" max="1">
                                            <button id="reset" onclick="resetWeight(`+i+`)" type="button"><i class="fas fa-times"></i></button>
                                            

                                        </div>
                                        <div class="settingsPage factorDescription">
                                            <p>`+factorDescription+`</p>
                                        </div>
                                </div>
                                <div style="clear: both"></div>`);
    }

    var weights = localStorage.getItem("weights");
    if(weights != null){  
        loadPrevWeights();
    }
    else{
        balanceWeights();
    }
}

function sliderInput(index, sliderValue){
    entryID = "NumInp"+index; // creates numerical input ID
    $("#"+entryID).val(sliderValue); // sets numerical input to slider value
}

function entryInput(index, entryValue){
    sliderID = "slider"+index; // creates slider ID
    $("#"+sliderID).val(entryValue); // sets slider to numerical input value
}

function acceptChanges(){
    sliders = $(".slider"); // collects slider elements

    weights = {}
    // iterates through sliders
    for(var index=0; index < sliders.length; index++){
        sliderID = sliders[index].id; // collects sliders id
        sliderValue = $("#"+sliderID).val(); // collectes slider value
        headerID = "Header"+index; // creates header id
        factorName = $("#"+headerID).html(); // collectes factor name
        weights[factorName] = sliderValue; // stores factor / weight pair in weights dict
    }

    localStorage.setItem("weights", JSON.stringify(weights)); // stores weights dict in localstorage
}

// loads previous weight configuration
function loadPrevWeights(){
    sliders = $(".slider"); // collect slider elements

    // iterates through slider elements
    for(var index=0; index < sliders.length; index++){
        sliderID = sliders[index].id; // collects sliders id
        headerID = "Header"+index; // creates header id
        factorName = $("#"+headerID).html() // collectes factor name
        weights = JSON.parse(localStorage.getItem("weights")); // loads weights dict
        value = weights[factorName]; // collects weight for factor
        $("#"+sliderID).val(value); // sets slider as weight
        entryID = "NumInp"+index; // creates numerical input ID
        $("#"+entryID).val(value); // sets numerical input as weight
    }
}

function resetWeight(index){
    entryID = "NumInp"+index;
    sliderID = "slider"+index;
    $("#"+entryID).val(0);
    $("#"+sliderID).val(0);
}

//function balanceWeights(){
//    sliders = $(".slider");
//    for(var index=0; index < sliders.length; index++){
//        sliderID = sliders[index].id;
//        value = 0;
//        $("#"+sliderID).val(value);
//       entryID = "NumInp"+index;
//        $("#"+entryID).val(value);
//    }
//}

// sets weights to default value
function balanceWeights(){
    sliders = $(".slider"); // collects slider elements

    // iterates through sliders
    for(var index=0; index < sliders.length; index++){
        sliderID = sliders[index].id; // collects sliders id
        value = factorData[index]["defaultWeight"]; // collects default weight
        $("#"+sliderID).val(value); // sets slider to default weight
        entryID = "NumInp"+index; // creates numerical input ID
        $("#"+entryID).val(value); // sets numerical input to default weight
    }
}

function resize(){
    var containerSize = window.innerHeight - $("#header").height() - $("#pageControlsContainer").height()-20;
    $('#resultsContainer').css('min-height', containerSize);
    //console.log("hola");
}





var pageSize = 10; // Defines the number of result items on each page.


function goToTop(){
    $('html, body').animate({ scrollTop: 0 }, 'fast');
}

function displayWidget(searchResults){
    var title = searchResults["widget"]["title"];
    var description = searchResults["widget"]["description"];
    var url = searchResults["widget"]["url"];
    var image = searchResults["widget"]["image"];
    if(image==null){
        $("#widgetContainer").append('<div id="widget"><div id="header"><img><div id="details"><h1>'+title+'</h1></div></div><p id="widgetDescription">'+description+'</p><a href="'+url+'">Read More at Wikipedia...</a></div>');
        $("#widget img").css({"border-style":"none", "height":"2vw", "width": "0px"});
        $("#widget #details").css({"left":"0px"})
    }
    else{
        $("#widgetContainer").append('<div id="widget"><div id="header"><img src='+image+'><div id="details"><h1>'+title+'</h1></div></div><p id="widgetDescription">'+description+'</p><a href="'+url+'">Read More at Wikipedia...</a></div>');
    }
}

function displayResult(result, index){ // Displays the data in a given JSON result object.
    // unpacks JSON object
    console.log(result);
    var details = result.details;
    var title = details.title;
    var url = details.url;
    var domain = details.domain;
    var description = details.description;
    var scores = result.scores;
    var favicon = details.favicon;

    // Displays the results info from the JSON object. 
    if(favicon!=null){
        $("#resultsList").append('<div class="result" id="result'+index+'"> <div class="content"> <a href="'+url+'" class="title">'+title+'</a> <div id="wrapper"> <img class="favicon" src="'+favicon+'"> <p class="domain">'+domain+'</p> </div> <p class="description">'+description+'</p> </div><button name="'+index+'" id="moreStats'+index+'" class="moreStats" type="button"><i id="vertEllipsis" class="fas fa-ellipsis-v"></i></button> </div>');
    }
    else{
        $("#resultsList").append('<div class="result" id="result'+index+'"> <div class="content"> <a href="'+url+'" class="title">'+title+'</a> <div id="wrapper">  <p class="domain">'+domain+'</p> </div> <p class="description">'+description+'</p> </div><button name="'+index+'" id="moreStats'+index+'" class="moreStats" type="button"><i id="vertEllipsis" class="fas fa-ellipsis-v"></i></button> </div>');
    }
    
    // creates empty extra stats window
    position = index+1;
    $("#result"+index+"").append('<div id="popupWrapper'+index+'" class="popupWrapper"><div class="pointer"><div class="pointerOutline"></div><div class="pointerInner"></div></div> <div id="window'+index+'" class="extraStatsWindow"> </div></div>');
    

    // figures out what position header to display and whether to display a crown
    if(index==0){
        $("#window"+index).append('<h1 class="rating">1st <i id="first" class="fas fa-crown"></i></h1>')
    }
    else if(index==1){
        $("#window"+index).append('<h1 class="rating">2nd <i id="second" class="fas fa-crown"></i></h1>')
    }
    else if(index==2){
        $("#window"+index).append('<h1 class="rating">3rd <i id="third" class="fas fa-crown"></i></h1>')

    }
    else{
        if(position>20 || position<10){
            lastDigit = position%10;
            if(lastDigit==1){
                suffix = "st";
            }
            else if(lastDigit==2){
                suffix = "nd";
            }
            else if(lastDigit==3){
                suffix = "rd";
            }
            else{
                suffix="th";
            }
        }
        else{
            suffix="th";
        }
        $("#window"+index).append('<h1 class="rating">'+position+suffix+'</h1>')
    }
    
    
    // Populates the pop-up with the information from the JSON object.
    for (var header in scores){
        var value = scores[header];
        var number = parseFloat(value);
        if(number<0){
            var polarity = "negative";
        }
        else{
            var polarity = "positive";
        }
        $("#window"+index+"").append('<p class="ratingHeader">'+header+': <span class="'+polarity+'" class="rating">'+value+'</span></p>');
    }
}

function setLightDarkMode(mode){
    if(mode=="dark"){
        $("html").removeClass("lightMode").addClass("darkMode");
        $("#light-darkIcon").removeClass("fas fa-sun").addClass("fas fa-moon");
    }
    else{
        $("html").removeClass("darkMode").addClass("lightMode");
        $("#light-darkIcon").removeClass("fas fa-moon").addClass("fas fa-sun");
    }
}

function loadResultsPage(pageNum, scrollButtonState){ // Loads the results of a given page.  
    
    //$("#resultsList").html(""); // clears list of results

    $( "#resultsList .result").remove();

    // If the scroll-type is paged then the results for the given page are displayed.
    if(scrollButtonState=="paged"){
        
        $("#pageNum").html(pageNum); // Updates page number text
        if(pageNum==1){
            $(".fas.fa-arrow-left").css({"color":"var(--main-disabled-color)"}); // disables back button
            $("#backButton").css({"pointer-events":"none"});
            
            if(suggestion==true){
                $("#suggestionBar").show();
            }

            if(widget == true){
                $("body").removeClass("noWidgetPage").addClass("widgetPage");
                $("#widget").show(); // Shows widget and disables back button if it is the first page
            }
            else{
                $("body").removeClass("widgetPage").addClass("noWidgetPage");
                $("#widget").hide(); // Shows widget and disables back button if it is the first page
            }
            
        }
        else{ // Hides widget and enables back button if it isn't the first page
            $(".fas.fa-arrow-left").css({"color":"var(--main-active-color)"}); // enables back button
            $("#backButton").css({"pointer-events":"auto"});
            $("body").removeClass("widgetPage").addClass("noWidgetPage");
            $("#widget").hide();
            $("#suggestionBar").hide();
        }


        if (pageNum==lastPage){
            $(".fas.fa-arrow-right").css({"color":"var(--main-disabled-color)"}); // disables forward button
            $("#forwardButton").css({"pointer-events":"none"});
        }
        else{
            $(".fas.fa-arrow-right").css({"color":"var(--main-active-color)"}); // enables forward button
            $("#forwardButton").css({"pointer-events":"auto"});
        }
        

        // Determines the index of the first and last items to be displayed on that page.
        startItem=(pageNum*pageSize)-pageSize;
        endItem = (pageNum*pageSize)-1; 

        // offsets endItem if the page isn't full
        length = searchResults["list"].length;
        if(endItem > length-1){
            endItem = length-1
        }
            
        // Loops through the JSON displaying the results on that page.

        for(var i=startItem; i <= endItem; i++){
            var result = searchResults["list"][i];
            displayResult(result, i);
            
        }
    }

    // If the scroll-type is infinity then all the results are displayed.
    else{
        if(widget==true){  
            $("#widget").show(); // Shows widget.
            $("body").removeClass("noWidgetPage").addClass("widgetPage");
        }
        else{
            $("#widget").hide();
            $("body").removeClass("widgetPage").addClass("noWidgetPage");
        }
        

        var total = searchResults["list"].length;
        lastItem = total-1;

        // Displays all results.
        for(var i=0; i < total; i++){
            var result = searchResults["list"][i];
            displayResult(result, i);
        }
    }
}


function originalSearch(){
    $("searchbar").val($("#suggestionLink").text());
    localStorage.setItem("autocorrect", 0);
    location.reload();
}

function returnValue(){
    return userCC;
}


function getCountryCode(){
    fetch('https://api.ipregistry.co/?key=b9ephs988uhqif7u').then(function(response) {
        return response.json();
    }).then(function(json) {
        userCC = json["location"]["country"]["code"];
        sendSearch(userCC);
    })
}

function waitForIt(){
    console.log(finished);
    if (finished==false) {
        setTimeout(function(){waitForIt()},100);
    };
}

function sendSearch(userCC){
    var urlParams = new URLSearchParams(window.location.search);
    var query = urlParams.get('query');
    var autocorrect = localStorage.getItem("autocorrect");
    var scrollButtonState = localStorage.getItem("scrollType");
    setScrollType(scrollButtonState);

    //in the event that the search settings page hasnt been visited this goes to smack
    var weights = JSON.parse(localStorage.getItem("weights"));
    var otherAttributes = {"query": query, "location": userCC, "autocorrect": autocorrect};
    console.log(otherAttributes);
    var queryStringJSON = $.extend(otherAttributes, weights);
    var queryString = new URLSearchParams(queryStringJSON).toString();
    var url='http://127.0.0.1:5000/makeSearch';
    console.log(url);

    searchStartTime = Date.now();

    $.ajax({
        type: "POST",
        url: url,
        headers: {
            'Content-type':'application/json', 
            'Accept':'application/json'
        },
        data: JSON.stringify({
            "query": query,
            "location": userCC,
            "autocorrect": autocorrect,
            "weights": weights
        }),
        success: function (data,status,xhr) {   // success callback function
            searchResults = data;
            console.log(searchResults)
            lastPage = Math.ceil(searchResults["list"].length/pageSize);

            // defines widget associated page features
            if(searchResults["widget"] != ""){
                widget = true;
                $("body").removeClass("noWidgetPage").addClass("widgetPage");
                $("#widget").show();
            }
            else{
                widget = false;
                $("body").removeClass("widgetPage").addClass("noWidgetPage");
                $("#widget").hide();
            }

            console.log(searchResults["widget"]);
            // Populates the widget with info from the JSON object.
            if(searchResults["widget"] != ""){
                displayWidget(searchResults);
            }

            
            suggestion = false;
            correctedQuery = searchResults["correctedQuery"]
            if(correctedQuery!=""){
                $("#searchbar").val(correctedQuery);
                $("#correctQueryLabel").text(correctedQuery);
                $("#suggestionLink").text(query);
                suggestion = true;
                $("#suggestionBar").show();
            }

            $(".sk-circle").hide();
            if(searchResults["list"]!=""){
                searchEndTime = Date.now();
                $("#searchTime").text((searchEndTime - searchStartTime)/1000);
                $("#resultNum").text(searchResults["list"].length);
                $("#timingMessage").show();
                loadResultsPage(1, scrollButtonState);
            }
            else{
                $("#noResultsMessage").show();
                $("#noResultsQuery").text(query);
                $("#pageControlsContainer").hide();
            }
        },
        dataType: "json"
      });
    localStorage.setItem("autocorrect", 1);
}



$(document).ready(function(){ // Runs when the page starts...

    var locationPerms = localStorage.getItem("locationPerms");
    if(locationPerms == undefined){
        if (confirm('Allow Googleplex to Access Your Location?')) {
            localStorage.setItem("locationPerms", true);
          } else {
            localStorage.setItem("locationPerms", false);
          }
    }

     $(".searchbar").on('keypress',function(e) {
        query = $(this).val()
        if(e.which == 13 && query.trim()!="") {  
            location.href = "ResultsPage.html?query="+query;
        }
    });
    

    var lightDarkButtonState = localStorage.getItem("lightDarkState"); // Gets the last used scroll-type from the web browser.
    setLightDarkMode(lightDarkButtonState);

    page = $("body").attr("class").split(' ')[0];
    //setting page stuff
    if (page=="settingsPage"){


        $.ajax('http://127.0.0.1:5000/getFactor', 
        {
            dataType: 'json', // type of response data
            success: function (data,status,xhr) {   // success callback function
                factorData = data;
                loadSettingsPage();
            },
            error: function (jqXhr, textStatus, errorMessage) { // error callback 
                console.log('Error: ' + errorMessage);
            }
        });
    }
    else if (page=="resultsPage"){
        console.log("results page")

        if (localStorage.getItem("autocorrect")==null) {
            localStorage.setItem("autocorrect", 1);
        }


        resize();
        var urlParams = new URLSearchParams(window.location.search);
        var query = urlParams.get('query');
        var page = urlParams.get('page'); // extracts "page" value from query strings



        if(query==null){
            if(page=="Settings"){
                var query = localStorage.getItem("lastQuery");
                urlParams.set('query', query);
                window.location.search = urlParams;
            }
            else{
                location.href = "HomePage.html";
            }
        }

        if(query==null){
            location.href = "HomePage.html";
        }

        localStorage.setItem("lastQuery", query)

        $("title").html(query);
        $("#searchbar").val(query);


        locationPerms = false;
        if(locationPerms==true){
            userCC = getCountryCode();
        }
        else{
            sendSearch(null);
        }



}
});

function makeSearch(){
    query = $("searchbar").val()
    location.href = "ResultsPage.html?query="+query;
}

function forwardPage(){ // Displays next page...
    var pageNum = $("#pageNum").html(); // gets current page number
    var nextPage=parseInt(pageNum)+1; // calculates new page number
    loadResultsPage(nextPage, "paged"); // loads new page
} 
 
function backPage(){ // Displays previous page.
    var pageNum = $("#pageNum").html();// gets current page number
    var nextPage=parseInt(pageNum)-1; // calculates new page number
    loadResultsPage(nextPage, "paged");// loads new page
} 

function setScrollType(scrollType){
    if(scrollType=="paged"){
        $("#scrollIcon").removeClass("fas fa-infinity").addClass("fas fa-copy"); // changes button icon
        $("#pageControlsContainer").show(); // Shows page controls.
    }
    else if (scrollType=="infinity"){
        $("#scrollIcon").removeClass("fas fa-copy").addClass("fas fa-infinity"); // changes button icon
        $("#pageControlsContainer").hide(); // Hides page controls.
    }
}
function changeScrollType(){ // Switches between different scroll types.
    var scrollButtonState = localStorage.getItem("scrollType"); // Gets the last used scroll-type from the web browser.

    if (scrollButtonState=="infinity"){ // If previous scroll-type is infinity...
        scrollButtonState = "paged";
    }
    else{
        scrollButtonState = "infinity";
    }        
    setScrollType(scrollButtonState);
    localStorage.setItem("scrollType", scrollButtonState); // Updates the last used scroll-type.   
    loadResultsPage(1, scrollButtonState);        
}

$(document).on("click", function(event){ //When a mouse click occurs...
    var id = event.target.id; // Get the ID of the element clicked.
    var className = event.target.className;
        
    //After the pop-up is displayed a click anywhere on the page removes the shade from the button and hides the dropdown.
    if($(".extraStatsWindow").is(":visible")){
        $(".popupWrapper").hide();
        $(".extraStatsWindow").css({"top":0});
        $(".moreStats").removeClass("buttonBackground");
    }

    else{
        // Shows extra stats window and adds shadow to button when pressed.
        if(className=="moreStats" || id=="vertEllipsis"){
                if(id=="vertEllipsis"){
                    var id=event.target.parentElement.id;
                }

            index = document.getElementById(id).name;
            var wrapperId = "#popupWrapper".concat(index);
            var buttonId = "#moreStats".concat(index);
            console.log(wrapperId);

            
            prevHeight = $("#resultsContainer").prop('scrollHeight');
            console.log(prevHeight);
            $(wrapperId).show();
            postHeight = $("#resultsContainer").prop('scrollHeight');
            console.log(postHeight);
            offset = prevHeight-postHeight;
            console.log(offset);
            if(offset<0){
                $("#window"+index).css({"top":prevHeight-postHeight-20});
            }
            console.log(prevHeight - postHeight);

        
        }

    }   
});




// ------------------- home page ---------------------------

function changeLightDark(){ // Toggles between light and dark mode.
    //$("#light-darkIcon").toggleClass("fas fa-sun fas fa-moon");

    var lightDarkButtonState = localStorage.getItem("lightDarkState"); // Gets the last used scroll-type from the web browser.

    if (lightDarkButtonState=="dark"){
        localStorage.setItem("lightDarkState", "light")
        setLightDarkMode("light");
    }
    else{
        localStorage.setItem("lightDarkState", "dark")
        setLightDarkMode("dark");
    }
                 
}


