import json
import time
import traceback

from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from trip_data.SingleTripData import SingleTripData

YEAR = 2023
FIRST_MONTH = 4
LAST_MONTH = 6

WAIT_IN_SECS_BETWEEN_CLICKS = 2
ELEMENT_TIMEOUT = 5

IGNORE_DAYS = ['Saturday', 'Sunday']
def parse_row_elements(row_elements):
    raw_event_date, event_time, station, transaction, raw_fare, details = list(map(lambda element: element.text, row_elements))

    fare = None if raw_fare == '' else float(raw_fare.split(' ')[1].replace(',', '.'))
    week_day, event_date = event_time.split(' ')
    return SingleTripData(week_day, event_date, event_time, station, transaction, fare, details)

def main():
    print('Opening browser')

    try:
        chrome_service = Service('./chromedriver')
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.set_capability('unhandledPromptBehavior', 'accept')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36')
        browser = webdriver.Chrome(service=chrome_service, options=options)
        browser.delete_all_cookies()
        browser.execute_script("location.reload(true);")
    except Exception:
        traceback.print_exc()
        print('Failed to load chromedriver. Exiting.')
        exit()

    while True:
        browser.get('https://www.ov-chipkaart.nl/en/my-ov-chip/my-travel-history')
        WebDriverWait(browser, ELEMENT_TIMEOUT).until(lambda _: ('authenticationendpoint' in browser.current_url) or (browser.find_element(By.CLASS_NAME, "sga5ez3")))
        if 'authenticationendpoint' in browser.current_url:
            print('Please login and press Enter.')
            input()
        else:
            break

    card_div = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CLASS_NAME, "sga5ez3"))
    )
    card_div.click()
    time.sleep(WAIT_IN_SECS_BETWEEN_CLICKS)

    transaction_type = Select(WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.CLASS_NAME, "oe1wjn0"))
    ))
    transaction_type.select_by_index(1)

    time.sleep(WAIT_IN_SECS_BETWEEN_CLICKS)

    from_date = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
        expected_conditions.visibility_of_element_located((By.ID, "startDate"))
    )

    travel_data = []


    for month in range(FIRST_MONTH, LAST_MONTH + 1):
        search_date = f'{1}-{month}-{YEAR}'
        print(f'Searching for data on month {month} of {YEAR}')
        while not from_date.get_attribute('value') == "":
            from_date.send_keys(Keys.BACK_SPACE)
        from_date.send_keys(search_date)
        from_date.send_keys(Keys.ESCAPE)

        try:
            table_elements = WebDriverWait(browser, WAIT_IN_SECS_BETWEEN_CLICKS).until(
                expected_conditions.visibility_of_all_elements_located((By.CLASS_NAME, 'ag-cell'))
            )

            select_all_checkbox = WebDriverWait(browser, ELEMENT_TIMEOUT).until(
                expected_conditions.presence_of_element_located((By.ID, 'ag-5-input'))
            )
            select_all_checkbox.click()

            for i in range(0, len(table_elements), 6):
                single_trip_data = parse_row_elements(table_elements[i:i + 6])
                # TODO: select only relevant checkboxes

            # TODO: download the pdf

        except Exception:
            print(f'No data found on month {month} of {YEAR}')
            continue

    with open('data.json', 'w') as file:
        file.write(json.dumps(travel_data))


if __name__ == '__main__':
    main()