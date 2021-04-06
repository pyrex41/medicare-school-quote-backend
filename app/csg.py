import requests, json
from babel.numbers import format_currency as format_currency_verbose
from datetime import datetime, timedelta
from toolz.functoolz import pipe
from decimal import Decimal
import os
import configparser
from collections import OrderedDict


def format_currency(n):
    return format_currency_verbose(n, 'USD', locale='en_US')

def format_rates(quotes, household = False):
    d = []
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
        #plan = q['plan']

        has_h = 'household' in kk.lower()

        if naic == '79413': # workaround for UHC levels
            if 'level 1' in kk.lower():
                naic = naic + '001'
            elif 'level 2' in kk.lower():
                naic = naic + '002'

            if bool(household) == has_h:
                d.append((kk, rate, naic))
        elif naic == '88366': # workaround for CIGNA substandard
            if 'substandard' in kk.lower():
                naic = naic + '001'
                if has_h:
                    if bool(household) == has_h:
                        d.append((kk, rate, naic))
                else:
                    d.append((kk, rate, naic))
        else:
            if has_h: # workaround for Humana // Household
                if bool(household) == has_h:
                    d.append((kk, rate, naic))
            else:
                d.append((kk, rate, naic))

    slist = sorted(d, key=lambda x: x[1])
    out_list = []
    for k,v,n in slist:
        out_list.append({
            'company'   : k,
            'rate'      : format_currency(v/100),
            'naic'      : n,
            'plan'      : plan
        })
    return out_list

def format_pdp(pdp_results, year):
    out = []
    for pdpr in pdp_results:
        info = {
            'Plan Name': pdpr['plan_name'],
            'Plan Type': pdpr['plan_type'],
            'State': pdpr['state'],
            'rate': format_currency(pdpr['month_rate']/100),
            'year': int(year.strftime("%Y"))
        }
        out.append(info)
    return out

def filter_quote(quote_resp, household = False, custom_naic=None, select=False):
        fresp = list(filter(lambda x: x['select'] == False, quote_resp)) if not select else quote_resp

        if custom_naic:
            return pipe(
                    list(filter(lambda x: int(x['company_base']['naic']) in custom_naic,fresp)),
                    format_rates)
        else:
            return format_rates(fresp, household = household)

class csgRequest:
    def __init__(self, api_key):
        self.uri = 'https://csgapi.appspot.com/v1/'
        self.api_key = api_key
        try:
            self.set_token(self.parse_token('token.txt'))
        except:
            self.set_token()

    def parse_token(self, file_name):
        parser = configparser.ConfigParser()
        parser.read('token.txt')
        return parser.get('token-config', 'token')

    def set_token(self, token=None):
        self.token = token if token else self.fetch_token()

        try:
            os.remove("token.txt")
        except:
            pass

        with open("token.txt", "w+") as my_file:
            my_file.write("[token-config]\n")
            my_file.write("token={}".format(self.token))

    def GET_headers(self):
        return {
            'Content-Type': 'application/json',
            'x-api-token': self.token
        }

    def fetch_token(self):
        ep = 'auth.json'
        values = json.dumps({'api_key': self.api_key})
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(self.uri + ep, data = values, headers = headers)
        jr = resp.json()
        # add error handling if too many sessions
        token = jr['token']


        return token

    def reset_token(self):
        print('resetting token')
        self.set_token(token=None)

    def get(self, uri, params):
        resp = requests.get(uri, params=params, headers=self.GET_headers())

        if resp.status_code == 403:
            self.reset_token()
            return requests.get(uri, params=params, headers=self.GET_headers())
        elif resp.status_code == 400:
            # Adding this to deal with situation where county name is malformed.
            # May not properly address hypothetical situation where there are different
            # prices intra-zip code based on county.
            try:
                params.pop('county')
                return requests.get(uri, params=params, headers=self.GET_headers())
            except:
                return resp
        else:
            return resp

    def _fetch_pdp(self, zip5, effective_date):
        ep = 'medicare_advantage/quotes.json'
        '''
        effective_date = pipe(
            datetime.now(),
            lambda x: x.year,
            str,
        )
        '''
        payload = {
            'zip5': zip5,
            'plan': 'pdp',
            'effective_date': effective_date
        }
        resp = self.get(self.uri + ep, params=payload)
        return resp

    def fetch_pdp(self, zip5, year1, year2):
        now_trim = datetime.replace(datetime.now(), microsecond=0, minute=0, second=0, hour=0) + timedelta(days=1)
        _r1 = datetime(year1, 1, 1, 0, 0)
        year1 = max(now_trim, _r1)
        y1 = year1.strftime("%Y-%m-%dT%H:%M:%S")
        year2 = datetime(year2, 1, 1, 0, 0)
        y2 = year2.strftime("%Y-%m-%dT%H:%M:%S")
        resp1 = self._fetch_pdp(zip5, y1).json()
        resp2 = self._fetch_pdp(zip5, y2).json()
        fresp1 = format_pdp(resp1, year1)
        fresp2 = format_pdp(resp2, year2)
        return fresp1 + fresp2

    def fetch_quote(self, **kwargs):
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
        resp = self.get(self.uri + ep, params=payload)
        return resp.json()
    '''
    async def async_fetch_quote(self, **kwargs):
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
        return resp.json()
    '''
