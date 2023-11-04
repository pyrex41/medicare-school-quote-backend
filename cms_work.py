import requests
import os
import json
from pprint import pprint 

def post_request(url, data, headers):
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

