# used for credentials
import config
# used for sending and receiving data
import requests as requests
# used for extracting the special codes & extracting deadlines
from bs4 import BeautifulSoup
# used for storing cookies
import pickle
# as always time is always one of the most difficult/annoying things to handle in programming, why can't we have just
# one time library that does everything
import pytz
import datetime
from datetime import timedelta
# for writing the .ics files
from icalendar import Event, Calendar


#
# TL;DR This script downloads your deadlines (assuming you are a comp sci student) from the University of Manchester's
# SPOTv2 system and puts them in an ical file you can then import into any calendar application.

# Limitations:
# Since SPOT does not specify the year of the deadline this script will duplicate them across this and next year just to
# be sure you don't miss anything, because of this it is highly recommended you import the ical file into a new calendar
# you can delete without changing your main one!

# Alternate use:
# This code might be useful if you are trying to implement something that needs to log in to the University of
# Manchester's systems since it stores the authentication cookie which is needed to access systems, It might even work
# for systems behind the 2FA such as blackboard, but I have not tested it.

# Technical Info:
# I have only found one other implementation of the University of Manchester's login system on GitHub, but I wasn't able
# to get it working. It turns out the uni uses a strange login system. When you first load up the login page there are
# hidden inputs in the HTML named "lt" & "execution", their API expects these to be included in the post request where
# you send them the username and password. I guess this is to make it more difficult to brute force passwords, a little
# inconvenient I might add, but it probably helps.

# TODO I should probably make a smarter version which decides based upon the first deadline what year it is
# TODO I should probably extend this to use the check in system to automatically mark me present, or at least give me
#  a reminder


# object-oriented programming is nice
class Deadline:
    def __init__(self, course_id, assessment_name, due_date):
        self.course_id = course_id
        self.assessment_name = assessment_name
        self.due_date = due_date


# This intermediary exists in case I decide to add Google calendar support later
class IntermediaryEvent:
    def __init__(self, name, begin, end):
        self.name = name
        self.begin = begin
        self.end = end


# This is the URL for the service you want to be redirected to after login, in my case its SPOT
login_url = "https://login.manchester.ac.uk/cas/login?service=https%3A%2F%2Fstudentnet.cs.manchester.ac.uk%2Fme%2Fspotv2%2Fspotv2.php"
# Gives you a wall of text for debugging
debug = False


# This function logs into the website, returning a requests' session with the cookies you will need to access SPOT or other uni systems
def login(local_login_url, local_username, local_password):
    # Getting the login HTML
    local_requests_session = requests.Session()
    response_html_login = local_requests_session.get(login_url)
    html_login_page = str(response_html_login.content)
    if (debug):
        print("Login page HTML response: " + html_login_page)

    # Getting the execution and lt values
    soup_login_page = BeautifulSoup(html_login_page, 'html.parser')
    # These are the weird execution & lt things that must be sent with the login form
    execution = soup_login_page.find(attrs={"name": "execution"})['value']
    lt = soup_login_page.find(attrs={"name": "lt"})['value']
    if (debug):
        print("execution: " + execution)
        print("lt: " + lt)

    # Sending off the API login request
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    # Not sure if "_eventId" & "submit" are necessary, but they are sent if you log in via the site
    data = {'username': local_username, 'password': local_password, 'lt': lt, 'execution': execution,
            '_eventId': "submit", 'submit': "Login"}
    response_api_login = local_requests_session.post(local_login_url, data=data, headers=headers)
    if (debug):
        print("response: " + str(response_api_login))
        print("response cookies: " + str(response_api_login.cookies.get_dict()))
        print("session cookies: " + str(local_requests_session.cookies.get_dict()))

    # Checking that we have the response we wanted
    # This throws an error if we don't get a 200 code
    if (response_api_login.status_code != 200):
        raise Exception("Did not get response code 200, code: " + str(response_html_login.status_code))
    # This throws an error is the password is incorrect
    if ("The credentials that you provided have not been accepted" in str(response_api_login.content)):
        raise Exception("User/pass not accepted by login system, check user/pass")
    # This throws an error if you haven't been redirected, and the site doesn't say login successful
    if ("login.manchester.ac.uk" in response_api_login.url) and not ("Login Successful" in str(response_api_login.content)):
        raise Exception("Login was unsuccessful for an unknown reason")

    return local_requests_session


# This saves the cookies as a data file, it should reduce the number of login requests
def save_cookies(local_requests_session, path):
    try:
        with open(path, 'wb') as f:
            pickle.dump(local_requests_session.cookies, f)
    finally:
        f.close()


# This loads the cookies from the data file
def load_cookies(path):
    local_requests_session = requests.session()
    try:
        with open(path, 'rb') as f:
            local_requests_session.cookies.update(pickle.load(f))
    finally:
        f.close()
        return local_requests_session


# This downloads the SPOT site which contains all the deadlines
# We give it the previous cookies from when we logged in or saved cookies, so we don't have to authenticate every time
def get_spot_html(local_requests_session):
    spot_url = "https://studentnet.cs.manchester.ac.uk/me/spotv2/spotv2.php"
    response_html_spot = local_requests_session.get(spot_url)

    # If we don't get 200 it means we probably aren't logged in, and we have been redirected to the login page
    if (response_html_spot.status_code != 200):
        raise Exception("Did not get response code 200, code: " + str(response_html_spot.status_code))
    if ("login.manchester.ac.uk" in response_html_spot.url):
        raise Exception("Not authorized, was redirected to login page")
        
    local_html_spot = response_html_spot.content
    if (debug):
        print("Spot page HTML response: " + str(local_html_spot))
    return local_html_spot


# This takes the HTML and gives us a big list of the deadlines in a nice easy form
def parse_deadlines(local_html_spot):
    soup_spot = BeautifulSoup(local_html_spot, 'html.parser')
    # This is the HTML table that contains all the deadlines
    soup_spot_deadlines_table = soup_spot.find(id="tblDeadlines")
    if (debug):
        print("Deadlines Table content: " + str(soup_spot_deadlines_table))

    # This gets us all the entries in that table
    soup_spot_deadlines = soup_spot_deadlines_table.findAll("tr", style="cursor: pointer;")
    deadlines = []

    # This turns all that nasty HTML into a nice python class
    for child in soup_spot_deadlines:

        course_id = child.contents[0].contents[0]
        assessment_name = child.contents[1].contents[0]
        # Rather annoyingly the due date doesn't contain a year
        due_date = child.contents[2].contents[0]
        if (debug):
            print("------------------------------")
            print("Full deadline HTML: " + str(child))
            print("Course ID: " + str(course_id))
            print("Assessment name: " + str(assessment_name))
            print("Due date: " + str(due_date))
        # Not a huge fan of having to name everything in functions local_..., I miss Java and its better scopes
        local_deadline = Deadline(course_id, assessment_name, due_date)
        deadlines.append(local_deadline)

    return deadlines


# Boring but necessary switch statement, it was not fun to type out...
def month_to_num(str_month):
    match str_month:
        case ("Jan"):
            return 1
        case ("Feb"):
            return 2
        case ("Mar"):
            return 3
        case ("Apr"):
            return 4
        case ("May"):
            return 5
        case ("Jun"):
            return 6
        case ("Jul"):
            return 7
        case ("Aug"):
            return 8
        case ("Sep"):
            return 9
        case ("Oct"):
            return 10
        case ("Nov"):
            return 11
        case ("Dec"):
            return 12


# This is where the spaghetti code begins
def convert_deadlines_to_intermediary(local_deadlines, length, mode):
    intermediary_events = []
    year = datetime.date.today().year
    if (debug):
        print("Current year: " + str(year))

    for local_deadline in local_deadlines:

        name = local_deadline.course_id + ": " + local_deadline.assessment_name
        # Would you believe this worked first time without having to print any of it out, I am finally a string manipulation expert!!! (ish)
        day = int(local_deadline.due_date[0:2])
        month = month_to_num(local_deadline.due_date[3:6])
        hour = int(local_deadline.due_date[7:9])
        min = int(local_deadline.due_date[10:12])

        # This is added because the uni does not specify the year in the due date so just to be safe its duplicated for this and next year
        # Make sure you run this on a disposable calendar, not your main one!!!
        # TODO I should probably make a smarter version which decides based upon the first deadline what year it is
        if (mode == "safe"):
            n = 2
        # If I ever get around to it this will be the intelligent auto mode
        else:
            n = 1

        for i in range(0, n):
            tz = pytz.timezone("Europe/London")
            begin = tz.localize(datetime.datetime(year + i, month, day, hour, min))
            # This adds the specified length to the event, I don't think icals support events of 0 length, but I have not tried
            end = tz.localize(datetime.datetime(year + i, month, day, hour, min)) + timedelta(minutes=length)
            intermediary_event = IntermediaryEvent(name, begin, end)
            intermediary_events.append(intermediary_event)

    return intermediary_events


# This puts our intermediary events into ical events
def intermediary_events_to_ical(intermediary_events, local_calendar):
    for intermediary_event in intermediary_events:
        event = Event()
        event.add('summary', intermediary_event.name)
        event.add('dtstart', intermediary_event.begin)
        event.add('dtend', intermediary_event.end)
        event.add('dtend', intermediary_event.end)
        local_calendar.add_component(event)


# We try to log in via cookies first to reduce API calls
try:
    print("Attempting to load cookies")
    requests_session = load_cookies("Cookies.data")
    html_spot = get_spot_html(requests_session)
    deadlines = parse_deadlines(html_spot)
    print("Login using cookies successful")
# If that fails we log in using the user/pass stored in config.py
except Exception as e:
    print("Error! " + str(e))
    print("Login using cookies unsuccessful, trying using user/pass")
    requests_session = login(login_url, config.username, config.password)
    html_spot = get_spot_html(requests_session)
    print("Login using user/pass successful, saving to Cookies.data")
    save_cookies(requests_session, "Cookies.data")
    deadlines = parse_deadlines(html_spot)

# This shows you what it found on SPOT
for deadline in deadlines:
    print("------------------------------")
    print("Course ID: " + str(deadline.course_id))
    print("Assessment name: " + str(deadline.assessment_name))
    print("Due date: " + str(deadline.due_date))

# 60 is the length in min of the deadline, so a deadline at 18:00 will show as an event from 18:00 to 19:00
# safe means it will duplicate the deadlines this year and next year, since the uni doesn't specify the year in the due date
# anything other than "safe", and it will only do this year, so watch out!
inter_events = convert_deadlines_to_intermediary(deadlines, 60, "safe")
calendar = Calendar()
intermediary_events_to_ical(inter_events, calendar)
f = open('example.ics', 'wb')
f.write(calendar.to_ical())
f.close()
print("Done!!!")
