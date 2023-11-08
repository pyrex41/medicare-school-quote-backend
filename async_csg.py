import httpx
from httpx import ReadTimeout

from toolz.functoolz import pipe
from datetime import datetime
import configparser
from copy import copy
import asyncio
from babel.numbers import format_currency

from config import Config

import time
from pprint import pprint
import csv
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv

import bmemcached
import os

servers = os.environ.get('MEMCACHIER_SERVERS', '').split(',')
user = os.environ.get('MEMCACHIER_USERNAME', '')
passw = os.environ.get('MEMCACHIER_PASSWORD', '')

mc = bmemcached.Client(servers, username=user, password=passw)

mc.enable_retry_delay(True)  # Enabled by default. Sets retry delay to 5s.


# Set a value in Memcache


def fetch_sheet_and_export_to_csv():

    creds_file = "credentials.json"
    sheet_url = "https://docs.google.com/spreadsheets/d/1xg8p-aWEfzcTllZnILUY3-7oxC1hOgwBnzLeoUfbUhA"
    csv_filename = "cat.csv"
    
    # Setup the credentials
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
    client = gspread.authorize(creds)

    # Open the sheet by URL
    sheet = client.open_by_url(sheet_url).sheet1

    # Get all values from the sheet
    values = sheet.get_all_values()

    # ignore first 10 rows
    values = values[10:]

    # Check if the first row has the required headers
    if values and values[0][:3] == ["Category", "ID", "Name"]:
        # Write the values to a CSV file
        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(values)
        
        logging.info("Data successfully written to CSV file")
        pprint("Saved!")
        
    else:
        logging.error("Header validation failed. The CSV was not saved.")



def rate_limited(interval):
    def decorator(function):
        last_called = [0.0]
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed >= interval:
                last_called[0] = time.time()
                fetch_sheet_and_export_to_csv()
            return function(*args, **kwargs)
        return wrapper
    return decorator

fetch_sheet_and_export_to_csv()

def csv_to_dict(filename):
    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        result = {}
        for row in reader:
            # Convert 'Category' and 'ID' to integers
            row["Category"] = map_cat(row["Category"]) #int(row["Category"])
            # Check for null string key and filter it out
            if "" in row:
                del row[""]
            # Replace blank strings with None
            for key, value in row.items():
                if value == '':
                    row[key] = None
            result[row["ID"]] = row
    return result

def map_cat(a_or_b: str):
    if a_or_b.lower() == "a":
        return 0
    elif a_or_b.lower() == "b":
        return 1
    else:
        return 2

class AsyncCSGRequest:
    def __init__(self, api_key):
        self.uri = 'https://csgapi.appspot.com/v1/'
        self.api_key = api_key
        self.token = None  # Will be set asynchronously in an init method

    async def async_init(self):
        try:
            token = mc.get('csg_token')
            logging.info(f"Token: {token}")
            await self.set_token(token=token)
        except Exception as e:
            print(f"Could not get token somehow: {e}")
            await self.set_token()

    async def parse_token(self, file_name):
        # Assuming the token file contains a section [token-config] with a token entry
        
        """ 
        parser = configparser.ConfigParser()
        with open(file_name, 'r') as file:
            parser.read_file(file)
        return parser.get('token-config', 'token')
        """

    async def set_token(self, token=None):
        self.token = token if token else await self.fetch_token()
        # Token is set, no need to write to a file unless it's a new token
        if not token:
            # Write the token to 'token.txt' asynchronously
            mc.set('csg_token', self.token)
            """ 
            with open('token.txt', 'w') as f:
                f.write(f"[token-config]\ntoken={self.token}")
            """

    async def fetch_token(self):
        ep = 'auth.json'
        values = {'api_key': self.api_key}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.uri + ep, json=values)
            resp.raise_for_status()  # Will raise an exception for 4XX and 5XX status codes
            return resp.json()['token']

    def GET_headers(self):
        return {
            'Content-Type': 'application/json',
            'x-api-token': self.token
        }

    async def reset_token(self):
        print('Resetting token asynchronously')
        await self.set_token(token=None)

    async def get(self, uri, params):
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(uri, params=params, headers=self.GET_headers())
            if resp.status_code == 403:
                await self.reset_token()
                resp = await client.get(uri, params=params, headers=self.GET_headers())
            resp.raise_for_status()  # Will raise an exception for 4XX and 5XX status codes
            return resp.json()


    async def get(self, uri, params):
        for _ in range(3):  # Retry up to 3 times
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:  # Increase timeout
                    resp = await client.get(uri, params=params, headers=self.GET_headers())
                    if resp.status_code == 403:
                        await self.reset_token()
                        resp = await client.get(uri, params=params, headers=self.GET_headers())
                    resp.raise_for_status()  # Will raise an exception for 4XX and 5XX status codes
                    return resp.json()
            except ReadTimeout:
                print("Request timed out. Retrying...")
        raise Exception("Request failed after 3 attempts")

    async def _fetch_pdp(self, zip5):
        ep = 'medicare_advantage/quotes.json'
        payload = {
            'zip5': zip5,
            'plan': 'pdp',
        }
        resp = await self.get(self.uri + ep, params=payload)
        return resp

    async def fetch_pdp(self, zip5, *years):
        resp = await self._fetch_pdp(zip5)
        try:
            return self.format_pdp(resp, *years)
        except Exception as ee:
            emsg = {
                'Plan Name': "ERROR",
                'Plan Type': str(ee),
                'State': "CA",
                'rate': format_currency(0, 'USD', locale='en_US'),
                'year': list(years)[0]
            }
            return [emsg]
        
    def format_pdp(self, pdp_results, *_years):
        out = []
        years = list(_years)
        if len(years) == 0:
            years.append(datetime.today().year)
        for pdpr in pdp_results:
            dt_format = "%Y-%m-%dT%H:%M:%SZ"
            st_dt = pdpr['effective_date']
            dt = datetime.strptime(st_dt, dt_format)
            info = {
                'Plan Name': pdpr['plan_name'],
                'Plan Type': pdpr['plan_type'],
                'State': pdpr['state'],
                'rate': format_currency(pdpr['month_rate']/100, 'USD', locale='en_US'),
                'year': dt.year
            }
            out.append(info)
        fout = filter(lambda x: x['year'] in years, out)
        return list(fout)
    
    async def fetch_quote(self, **kwargs):
        acceptable_args = [
            'zip5',
            'county',
            'age',
            'gender',
            'tobacco',
            'plan',
            'select',
            'effective_date',
            'apply_discounts',
            'apply_fees',
            'offset',
            'naic'
        ]
        payload = {}

        for arg_name,val in kwargs.items():
            lowarg = arg_name.lower()
            if lowarg in acceptable_args:
                payload[lowarg] = val

        ep = 'med_supp/quotes.json'
        resp = await self.get(self.uri + ep, params=payload)
        return resp
    
    async def fetch_advantage(self, **kwargs):
        acceptable_args = [
            'zip5',
            'state',
            'county',
            'plan',
            'offset',   
            'effective_date',
            'sort',
            'order'
        ]
        payload = {}

        for arg_name,val in kwargs.items():
            lowarg = arg_name.lower()
            if lowarg in acceptable_args:
                payload[lowarg] = val

        if 'zip5' not in kwargs:
            raise ValueError("The 'zip5' argument is required.")

        ep = 'medicare_advantage/quotes.json'
        resp = await self.get(self.uri + ep, params=payload)
        return resp
    
    @rate_limited(3600)
    def format_rates(self, quotes, household):
        dic = {}
        for i,q in enumerate(quotes):
            rate = int(q['rate']['month'])
            naic = q['company_base']['naic']
            company_name = q['company_base']['name']
            plan = q['plan']

            if q['select']:
                k = company_name + ' // Select'
            else:
                k = company_name
            qq =q['rating_class']
            if qq:

                kk = k + ' // ' + q['rating_class']
            else:
                kk = k

            # workaround for those carriers in CSG that have multiple entries to handle discounts
            # may need something better if there's other reasons for multipe naic codes -- would require a rewrite
            arr = dic.get(naic, [])
            cat = 2
            disp = kk

            name_dict = csv_to_dict('cat.csv')

            ddic = name_dict.get(naic)
            if ddic:
                sub = False
                i = 1
                while i < 10:
                    s = str(i)
                    if ddic.get(s):
                        sval = ddic[s]
                        if sval.lower() in kk.lower():
                            naic = f"{naic}00{s}"
                            disp = f"{ddic.get('Name')} // {ddic.get(s, '').capitalize()}"
                            cat = 1
                            sub = True
                            break
                    i += 1
                if not sub:
                    cat = ddic.get("Category", 2)
                    disp = ddic.get("Name", kk)
                
            arr.append({
                "fullname": kk, 
                "rate": rate, 
                "naic": naic, 
                "category": cat, 
                "display": disp}
                )
            dic[naic] = arr

        # continued workaround for carriers in CSG that don't handle household correctly
        d = []
        for a in dic.values():
            if len(a) == 1: # this is the way it should work but CSG is pretty lame
                if bool(household):
                    d = d + a
                else:
                    # handling an edge case for Allstate where it returns a single "Rooommate" but doesn't put household in the fields
                    a_filt = list(filter(lambda x: has_household(x)==bool(household), a))
                    if len(a_filt) < len(a):
                        d = d + a_filt
                    else:
                        d = d + a
            else:
                # what about the case(s) where len(2) but they actually aren't putting household in the fields? Trying to handle that here
                a_filt = list(filter(lambda x: has_household(x)==bool(household), a))
                if len(a_filt) < len(a):
                    a_add = a_filt
                else:
                    a_add = a

                a_add = sorted(a_add, key = lambda x: "//" in x["fullname"])
                if len(a_add) > 1:
                    for i in range(1,len(a_add)):
                        a_add[i]["category"] = 1  # category 1 for anything after the first

                d = d + a_add
            


        slist = sorted(d, key=lambda x: x["rate"])
        out_list = []
        for dic in slist:
            out_list.append({
                'company'   : dic["fullname"],
                'rate'      : format_currency(dic["rate"]/100, 'USD', locale='en_US'),
                'naic'      : dic["naic"],
                'plan'      : plan,
                'category'  : dic["category"],
                'display'   : dic["display"]
            })
        return out_list
    
    def filter_quote(self, quote_resp, household = False, custom_naic=None, select=False):
        
        try:
            fresp = list(filter(lambda x: x['select'] == False, quote_resp)) if not select else quote_resp
        except Exception as e:
            logging.error(f"Error in filter_quote: {str(e)}")
            raise
        

        if custom_naic:
            return pipe(
                    list(filter(lambda x: int(x['company_base']['naic']) in custom_naic,fresp)),
                    self.format_rates)
        else:
            return self.format_rates(fresp, household = household)

    def format_results(self, results):
        row_dict = {}
        for r in results:
            for ol in r:
                company = ol['company']
                row = row_dict.get(company, {})
                row[ol['plan']] = ol['rate']
                row['naic'] = ol['naic']
                row['category'] = ol['category']
                row['display'] = ol['display']
                row_dict[company] = row

        rows = []
        for c,d in row_dict.items():
            row = {'company': c}
            row['F Rate'] = d.get('F', None)
            row['G Rate'] = d.get('G', None)
            row['N Rate'] = d.get('N', None)
            row['naic'] = int(d.get('naic', None))
            row['category'] = d.get('category', None)
            row['display'] = d.get('display', None)
            rows.append(row)
        return rows
    
    async def load_response(self, query_data, delay = None):
        if delay:
            await asyncio.sleep(delay)
        resp = await self.fetch_quote(**query_data)
        household = query_data.get("apply_discounts", False)
        return self.filter_quote(resp, household=household)
    
    async def load_response_all(self, query_data, delay = None):
        results = []
        plans_ = query_data.pop('plan')
        tasks = []
        p_actual = []
        for p in ['N', 'F', 'G']:
            if p in plans_:
                p_actual.append(p)
        for i,p in enumerate(p_actual):
            d = delay * i if delay else 0
            qu = copy(query_data)
            qu['plan'] = p
            tasks.append(self.load_response(qu, delay = d))

        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return self.format_results(results)
    
def has_household(x):
    kk = x["fullname"]
    nm = kk.lower()
    # Load name_dict from cat.csv
    name_dict = csv_to_dict('cat.csv')
    
    nm_list = set([x['Household'].lower() for x in name_dict.values() if x['Household']])
    for x in nm_list:
        if x in nm:
            return True
    return False


# Example usage
async def main():
    csg = AsyncCSGRequest(Config.API_KEY)
    await csg.async_init()
    # Example of making a request
    query_data = {
        'zip5': 62001, 
        'gender': 'M',
        'age': 65, 
        'county': 'MADISON', 
        'tobacco': 0, 
        'effective_date': '2023-12-01', 
        'plan': 'N'
    }
    response = await csg.load_response_all(query_data, delay=.2)
    return response

""" 
# Run the async main function           
r = lambda : asyncio.run(main())
import time
import statistics

from tqdm import tqdm

run_times = []
for _ in tqdm(range(20)):
    start_time = time.time()
    r()
    run_times.append(time.time() - start_time)

print("--- Min: %s seconds ---" % min(run_times))
print("--- Median: %s seconds ---" % statistics.median(run_times))
print("--- Max: %s seconds ---" % max(run_times))   
print("--- Mean: %s seconds ---" % statistics.mean(run_times))
"""