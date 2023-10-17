import os
import re
import time
import traceback
import PyPDF2
import calendar

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

# dates to search for relevant trips
YEAR = 2023
FIRST_MONTH = 3  # inclusive
LAST_MONTH = 10  # inclusive

STATIONS_TO_CHECK = ['Den Haag Centraal', 'Den Haag HS']  # station that is 100% in a trip to flag
STATIONS_AT_END = ['Diemen Zuid', 'Laan van Ypenburg', 'Station Diemen-Zuid']  # end stations in a trip to flag
STATIONS_AT_START = ['Diemen Zuid', 'Laan van Ypenburg']  # starting stations in a trip to flag

DECLARATIONS_DIR = os.getcwd() + '/declarations/'  # where pdf's are stored, directory must exist prior to running the script
CHROME_DATA_DIR = os.getcwd() + '/chrome_data/'
CHROME_DRIVER_PATH = os.getcwd() + '/chromedriver'

WAIT_FOR_DOWNLOAD = 5
WAIT_BETWEEN_CLICKS = 2
ELEMENT_TIMEOUT = 5


class Event:
    def __init__(self, checkbox, week_day, event_date, event_time, station, transaction, fare, details):
        self.checkbox = checkbox
        self.week_day = week_day
        self.event_date = event_date
        self.event_time = event_time
        self.station = station
        self.transaction = transaction
        self.fare = fare
        self.details = details


def parse_trip_table_row(row_elements):
    checkbox = row_elements[0].find_element(By.TAG_NAME, 'input')
    raw_event_date, event_time, station, transaction, raw_fare, details = list(map(lambda element: element.text, row_elements))

    fare = None if raw_fare == '' else float(raw_fare.split(' ')[1].replace(',', '.'))
    week_day, event_date = raw_event_date.split(' ')
    return Event(checkbox, week_day, event_date, event_time, station, transaction, fare, details)


def click(browser, element):
    browser.execute_script("arguments[0].click();", element)


def load_browser():
    try:
        chrome_service = Service(CHROME_DRIVER_PATH)
        options = webdriver.ChromeOptions()
        prefs = {"download.default_directory": DECLARATIONS_DIR}
        options.add_experimental_option('prefs', prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.set_capability('unhandledPromptBehavior', 'accept')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36')
        browser = webdriver.Chrome(service=chrome_service, options=options)
        browser.delete_all_cookies()
        browser.execute_script("location.reload(true);")
    except:
        traceback.print_exc()
        print('Failed to load chromedriver. Exiting.')
        exit()
    return browser


def is_authenticated(browser):
    browser.get('https://www.ov-chipkaart.nl/en/my-ov-chip/my-travel-history')
    WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        lambda _: ('authenticationendpoint' in browser.current_url) or (browser.find_element(By.CLASS_NAME, "sga5ez3")))
    return 'authenticationendpoint' not in browser.current_url


def go_to_trip_table(browser):
    card_div = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CLASS_NAME, "sga5ez3"))
    )
    click(browser, card_div)
    time.sleep(WAIT_BETWEEN_CLICKS)

    transaction_type = Select(WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CLASS_NAME, "oe1wjn0"))
    ))
    transaction_type.select_by_index(1)

    time.sleep(WAIT_BETWEEN_CLICKS)


def download_declaration_file(browser):
    create_declaration_button = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, ".vlfx9r0.vlfx9r1 .gg7hj10.gg7hj12.gg7hj19"))
    )

    if not create_declaration_button.is_enabled():
        return False

    click(browser, create_declaration_button)

    time.sleep(WAIT_BETWEEN_CLICKS)

    download_pdf_button = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, ".vlfx9r0.vlfx9r1 .gg7hj10.gg7hj12.gg7hj19"))
    )
    click(browser, download_pdf_button)
    return True

def is_declaration_file_download():
    time.sleep(WAIT_FOR_DOWNLOAD)
    return 'declaration' in ''.join(os.listdir(DECLARATIONS_DIR))

def back_to_trip_table(browser):
    back_to_history_button = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, ".vlfx9r0.vlfx9r1 .gg7hj10.gg7hj13.gg7hj19"))
    )
    click(browser, back_to_history_button)

    time.sleep(WAIT_BETWEEN_CLICKS)


def rename_declaration_file(month_of_declaration):
    file_to_rename = DECLARATIONS_DIR + [file_name for file_name in os.listdir(DECLARATIONS_DIR) if 'declaration' in file_name][0]
    declaration_text = PyPDF2.PdfReader(file_to_rename).pages[0].extract_text()
    total_fare = re.search('Total.expenses.€..(.*).Including', declaration_text).group(1)
    new_name = f'{DECLARATIONS_DIR}month_{month_of_declaration}_fare_{total_fare}eu.pdf'
    os.rename(file_to_rename, new_name)


def flag_relevant_events(browser, events):
    i = 0
    while i < len(events):
        single_trip_data = events[i]
        if single_trip_data.station in STATIONS_TO_CHECK:
            forward_pointer = back_pointer = i
            click(browser, single_trip_data.checkbox)

            while back_pointer - 1 >= 0:
                back_pointer -= 1
                previous_trip = events[back_pointer]
                if previous_trip.event_date != single_trip_data.event_date:
                    break
                if not previous_trip.checkbox.is_selected():
                    click(browser, previous_trip.checkbox)
                if previous_trip.station in STATIONS_AT_END:
                    break

            while forward_pointer + 1 < len(events):
                forward_pointer += 1
                next_trip = events[forward_pointer]
                if next_trip.event_date != single_trip_data.event_date:
                    break
                click(browser, next_trip.checkbox)
                if next_trip.station in STATIONS_AT_START:
                    break

            i = forward_pointer
        i += 1



def fetch_events_for_month(browser, month):
    from_date = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.ID, "startDate"))
    )

    to_date = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.ID, "endDate"))
    )

    start_date = f'{1}-{month}-{YEAR}'
    end_date = f'{calendar.monthrange(YEAR, month)[1]}-{month}-{YEAR}'

    while not from_date.get_attribute('value') == "":
        from_date.send_keys(Keys.BACK_SPACE)
    from_date.send_keys(start_date)
    from_date.send_keys(Keys.ESCAPE)

    while not to_date.get_attribute('value') == "":
        to_date.send_keys(Keys.BACK_SPACE)
    to_date.send_keys(end_date)
    to_date.send_keys(Keys.ESCAPE)

    try:
        table_elements = WebDriverWait(browser, WAIT_BETWEEN_CLICKS).until(
            expected_conditions.visibility_of_all_elements_located((By.CLASS_NAME, 'ag-cell'))
        )

        return [parse_trip_table_row(table_elements[i:i + 6]) for i in range(0, len(table_elements), 6)]
    except TimeoutException:
        return []


def deselect_all_events(browser):
    select_all_checkbox = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.presence_of_element_located((By.ID, 'ag-5-input'))
    )
    click(browser, select_all_checkbox)


def main():
    if not os.path.isdir(DECLARATIONS_DIR):
        print(f'Output director "{DECLARATIONS_DIR}" does\'t exist, please create the directory.')
        exit()

    print('Opening browser')
    browser = load_browser()

    while not is_authenticated(browser):
        print('Please login and press Enter.')
        input()

    go_to_trip_table(browser)

    for month in range(FIRST_MONTH, LAST_MONTH + 1):
        print(f'Searching for data on month {month} of {YEAR}')
        events = fetch_events_for_month(browser, month)
        if len(events) == 0:
            print(f'No data found on month {month} of {YEAR}')
            continue

        deselect_all_events(browser)

        flag_relevant_events(browser, events)

        print('Edit trip selection, press Enter to download declaration')
        input()

        print('Downloading declaration file')
        if not download_declaration_file(browser):
            print('No events selected, skipping')
            continue

        while not is_declaration_file_download():
            print('Declaration download hans\'t finished, waiting')

        back_to_trip_table(browser)

        print('Renaming declaration_file')
        rename_declaration_file(month)

    print('No more more months to search, exiting')

if __name__ == '__main__':
    main()
