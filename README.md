# SPOT-Scraper

## TL;DR 
This script downloads your deadlines (assuming you are a comp sci student) from the University of Manchester's SPOTv2 system and puts them in an ical file you can then import into any calendar application.

#### Limitations: 
Since SPOT does not specify the year of the deadline this script will duplicate them across this and next year just to be sure you don't miss anything, because of this it is highly recommended you import the ical file into a new calendar you can delete without changing your main one!

#### Alternate use: 
This code might be useful if you are trying to implement something that needs to log in to the University of Manchester's systems since it stores the authentication cookie which is needed to access systems, it might even work for systems behind the 2FA such as blackboard, but I have not tested it.

#### Technical info:
I have only found one other implementation of the University of Manchester's login system on GitHub, but I wasn't able to get it working. It turns out the uni uses a strange login system. When you first load up the login page there are hidden inputs in the HTML named "lt" & "execution", their API expects these to be included in the post request where you send them the username and password. I guess this is to make it more difficult to brute force passwords, a little inconvenient I might add, but it probably helps.
