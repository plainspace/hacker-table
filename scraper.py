import urllib2
import arrow
import os
from bs4 import BeautifulSoup
from model import Opentable, Reservation, connect_to_db, db
from server import app
import json

# Run 'source secrets.sh in terminal
# Get filepath for cronjob
filepath = os.environ['FILE_PATH']


# resto_list = [16609] # sample restaurant for testing scraper
person_list = [2, 4, 6]  # limit search options to 4 and 6 people


def restaurant_query():
    """Query database for restaurant IDs and return list of opentable IDs

    Sample Output:
    resto_list = [1906]"""

    opentable_id = db.session.query(Opentable.opentable_id).all()
    resto_list = []

    for restaurant in opentable_id:
        resto_list.append(restaurant[0])

    return resto_list


def current_time():
    """Create datetime object for current date and closest dates for Sat/Sun

    Sample Output:
    final_dates = ['08/13/2016', '08/14/2016']"""

    current_time = arrow.utcnow().to('US/Pacific')
    current_weekday = current_time.weekday()

    #check current day to get values of closest saturday and sunday
    if current_weekday < 5:
        first_sat = current_time.replace(days=+(5-current_weekday))
        first_sun = first_sat.replace(days=+1)
    elif current_weekday == 5:
        first_sat = current_time.replace(days=+7)
        first_sun = current_time.replace(days=+1)
    else:
        first_sat = current_time.replace(days=+6)
        first_sun = first_sat.replace(days=+1)

    #append first sat/sun in proper opentable URL format without changing arrow datetime object
    final_dates = [first_sat.format('MM/DD/YYYY'), first_sun.format('MM/DD/YYYY')]

    # append 1 more weekend to the final list of dates
    for i in range(1):
        first_sat = first_sat.replace(days=+7)
        first_sun = first_sun.replace(days=+7)
        final_dates.append(first_sat.format('MM/DD/YYYY'))
        final_dates.append(first_sun.format('MM/DD/YYYY'))

    return final_dates


def scrape_reservation_times(url):
    """Use Beautiful Soup to extract reservation times from given url

    Sample url: 'XXX'
    Sample Output:
    [opentable_id, date, people, times]
    [u'1906', u'08/13/2016', u'2', [u'12:30', u'1:00', u'11:30', u'11:45']]"""

    reservation_times = []

    url_output = urllib2.urlopen(url).read()

    # Only parse file if 'No tables available' not in html file
    if 'No tables are available' not in url_output:
        soup = BeautifulSoup(url_output, 'html.parser')  # create beautiful soup object
        available_times = soup.find_all('span', class_='t')  # get reservation times

        for x in available_times:
            x = x.text
            x = x.rstrip(' PM')  # delete extra string from times
            reservation_times.append(x)  # get text only from beautiful soup object

        #delete any blank or zero values
        reservation_times = filter(lambda a: a != u'\xa0', reservation_times)

    return reservation_times


def scrape_opentable(date_list, resto_list, person_list):
    """Create URLs for scraping, and call beautiful soup function to scrape times

    Loop over list for restos, persons, dates and scra
    Sample list of filenames = ['output_08132016_1906_2.html', 'output_08132016_1906_4.html']"""

    #initialize empty dictionary for final output
    reservation_dict = {}
    reservation_time = '%2012:00:00%20PM'  # use 12:00pm as default search time
    reservation_id = 1  # reservation_id is a counter to be used for dictionary key

    for date in date_list:
        for resto in resto_list:
            for person in person_list:
                url = 'http://opentable.com/opentables.aspx?t=rest&r=%i&d=%s%s&p=%i' % (resto, date, reservation_time, person)
                reservation_times = scrape_reservation_times(url)  # call scrape_reservation_times function on URL
                reservation_dict[reservation_id] = [resto, date, person, reservation_times]  # add item to dictionary per URL
                reservation_id = reservation_id + 1

    reservation_json = json.dumps(reservation_dict)
    with open(filepath + 'seed/reservation_json.json', 'wb') as output:
        output.write(reservation_json)

    return reservation_dict


def load_reservations():
    """Load reservations data to database from scraped data"""

    print "Loading Reservation data"

    #Delete all rows in table to reseed data every time this function is called
    Reservation.query.delete()

    #open json file and convert to dictionary for looping over
    reservation_dict = json.load(open(filepath + 'seed/reservation_json.json'))

    #loop over all items in dictionary to insert details to database
    for reservation_id, details in reservation_dict.items():
        reservation_id = reservation_id
        opentable_id = details[0]
        arrow_date = arrow.get(details[1], 'MM/DD/YYYY')  # convert string to datetime
        date = arrow_date.format('DD-MMM-YYYY')
        people = int(details[2])
        if len(details[3]) == 0:
            time = None  # if no reservations, assign Nonetype
        elif len(details[3]) >= 4:
            time = details[3][1:4]  # if many reservations available, get 3 only
        else:
            time = details[3]

        reservation = Reservation(reservation_id=reservation_id,
                                  opentable_id=opentable_id,
                                  date=date,
                                  people=people,
                                  time=time)

        #add opentable info to the database
        db.session.add(reservation)

    #commit work
    db.session.commit()


# #############################################################################
# Helper functions


if __name__ == "__main__":
    # User can work with database directly when run in interactive mode
    from server import app
    connect_to_db(app)
    print "Connected to DB."

    print arrow.utcnow().to('US/Pacific')
    # resto_list = restaurant_query()
    # print 'Creating date list'
    # date_list = current_time()
    # print 'Scraping open table'
    # scrape_opentable(date_list, resto_list, person_list)
    print 'Seeding database'
    load_reservations()
    print arrow.utcnow().to('US/Pacific')

