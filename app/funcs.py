from copy import copy
from csv import DictReader
from toolz.functoolz import pipe
from flask import jsonify

from app.csg import format_rates, format_pdp, filter_quote, csgRequest
from config import Config

'''
def my_filter(st, dic_list):
    out = []
    for d in dic_list:
        if st.upper() in d['company'].upper():
            out.append(d)
    pprint(out)
'''


api_key = Config.API_KEY
cr = csgRequest(api_key)

def load_response(query_data, verbose=True):
    resp = cr.fetch_quote(**query_data)
    household = query_data.get("apply_discounts", False)
    return filter_quote(resp, household=household, verbose=verbose)

def format_results(results):
    row_dict = {}
    for r in results:
        for ol in r:
            company = ol['company']
            row = row_dict.get(company, {})
            row[ol['plan']] = ol['rate']
            row['naic'] = ol['naic']
            row_dict[company] = row

    rows = []
    for c,d in row_dict.items():
        row = {'company': c}
        row['F Rate'] = d.get('F', None)
        row['G Rate'] = d.get('G', None)
        row['N Rate'] = d.get('N', None)
        row['naic'] = int(d.get('naic', None))
        rows.append(row)
    return rows

def load_response_all(query_data, verbose=True):

    #tasks = []
    results = []
    plans_ = query_data.pop('plan')
    for p in ['N', 'F', 'G']:
        qu = copy(query_data)
        if p in plans_:
            qu['plan'] = p
            results.append(load_response(qu, verbose=True))

    #results = await asyncio.gather(*tasks)

    return format_results(results)

class getZips():
    def __init__(self, file_name):
        self.zips = load_zips(file_name)

    def __call__(self, zip5):
        return lookup_zip(zip5, self.zips)

def lookup_zip(z, zdic):
    return zdic.get(str(z), ['None'])

def load_zips(file_name):
    zips = {}
    with open(file_name, mode='r') as cf:
        cr = DictReader(cf)
        first_row = True
        for row in cr:
            if first_row:
                first_row = False
            else:
                zips[(row['zip'])] = [i.upper() for i in row['county_names_all'].split('|')]
    return zips
