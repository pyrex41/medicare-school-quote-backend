#from pymongo import MongoClient
from copy import copy
from csv import DictReader
from toolz.functoolz import pipe

from csg import format_rates, format_pdp, filter_quote, csgRequest
from config import Config


api_key = Config.API_KEY
token = Config.CSG_TOKEN

cr = csgRequest(api_key, token=token)

def load_response(cr, query_data, naic=None, verbose=False):
    resp = cr.fetch_quote(**query_data)
    try:
        fq = filter_quote(resp, custom_naic=naic, select=False, verbose=verbose)
        out_list = []
        for k,v in fq.items():
            out_list.append({
                'company'   : k,
                'rate'      : v
            })
        return {
            'error' : None,
            'body' : out_list
        }
    except Exception as e:
        return {'error': str(e), 'body': resp}

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
