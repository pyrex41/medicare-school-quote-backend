import requests
import json
import os
import configparser

from funcs import format_pdp, filter_quote

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
        # todo -- add error handling if too many sessions
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

    def _fetch_pdp(self, zip5):
        ep = 'medicare_advantage/quotes.json'
        payload = {
            'zip5': zip5,
            'plan': 'pdp',
        }
        resp = self.get(self.uri + ep, params=payload)
        return resp

    def fetch_pdp(self, zip5, *years):
        resp = self._fetch_pdp(zip5).json()
        fresp = format_pdp(resp, *years)
        return fresp

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

    def load_response(self, query_data):
        resp = self.fetch_quote(**query_data)
        household = query_data.get("apply_discounts", False)
        return filter_quote(resp, household=household)