from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Importing the necessary modules as they were used in the Flask application
from async_csg import fetch_sheet_and_export_to_csv
from async_csg import AsyncCSGRequest as csg
from zips import zipHolder
from config import Config
from pprint import pprint
import logging

import bmemcached
import os

servers = os.environ.get('MEMCACHIER_SERVERS', '').split(',')
user = os.environ.get('MEMCACHIER_USERNAME', '')
passw = os.environ.get('MEMCACHIER_PASSWORD', '')

mc = bmemcached.Client(servers, username=user, password=passw)

mc.enable_retry_delay(True)  # Enabled by default. Sets retry delay to 5s.

# FastAPI app initialization
app = FastAPI()

# CORS middleware settings
origins = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://localhost:9000",
    "https://medicareschool-quote.netlify.app",
    "http://medicareschoolquote.com",
    "https://medicareschoolquote.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Assuming the API key and csgRequest instantiation are the same as in the Flask app
api_key = Config.API_KEY
cr = csg(api_key)

@app.on_event("startup")
async def startup_event():
    global cr
    cr = csg(api_key)
    await cr.async_init()


# Pydantic models for request parameters
class ZipArgs(BaseModel):
    zip: int
    show_state: Optional[bool] = False

class PDPArgs(BaseModel):
    zip: int
    year1: Optional[int]
    year2: Optional[int]

class PlansArgs(BaseModel):
    zip: int
    county: Optional[str] = None
    age: int
    gender: str
    tobacco: bool
    discounts: bool
    date: str
    plan: List[str]
    naic: Optional[List[str]] = None

# FastAPI endpoints using async
@app.get("/api/counties")
async def get_counties(zip: int = Query(..., description="The ZIP code to query"),
                       show_state: bool = Query(False, description="Whether to show the state or not")):
    zips = zipHolder('static/uszips.csv')
    county_list, state = zips(zip, show_state=True) if zip else (None, None)
    response = {'counties': county_list}
    if show_state:
        response['state'] = state
    return response

@app.get("/api/pdp")
async def get_pdp(zip: int = Query(..., description="ZIP code"),
                  year1: int = Query(None, description="Starting year"),
                  year2: int = Query(None, description="Ending year")):
    try:
        zip5 = str(zip).zfill(5)
        current_year = 2023  # This should be dynamically determined
        year1 = year1 if year1 else current_year
        year2 = year2 if year2 else current_year + 1
        if year1 < current_year or year2 < current_year + 1:
            raise HTTPException(status_code=400, detail="Invalid year parameters")
        resp = await cr.fetch_pdp(zip5, year1, year2)  # Assuming this is an async call
        return {'body': resp, 'error': None}
    except Exception as e:
        return {'body': [None], 'error': str(e)}


@app.get("/api/plans")
async def get_plans(zip: int = Query(..., description="ZIP code"),
                    county: str = Query(..., description="County"),
                    age: int = Query(..., description="Age"),
                    gender: str = Query(..., description="Gender"),
                    tobacco: bool = Query(..., description="Tobacco usage"),
                    discounts: bool = Query(..., description="Discounts"),
                    date: str = Query(..., description="Effective date"),
                    plan: List[str] = Query(..., description="Plan types")):
    try:
        args = {
            'zip': zip,
            'county': county,
            'age': age,
            'gender': gender,
            'tobacco': tobacco,
            'discounts': discounts,
            'date': date,
            'plan': plan
        }
        args['zip5'] = str(args.pop('zip')).zfill(5)
        args['effective_date'] = args.pop('date')
        def bool_int(a, new_field_name = None):
            b = args.pop(a)
            if new_field_name:
                args[new_field_name] = 0 if b == False else 1
            else:
                args[a] = 0 if b == False else 1

        bool_int('discounts', 'apply_discounts')
        bool_int('tobacco')

        results = await cr.load_response_all(args, delay=.2)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# The actual implementations of csgRequest, fetch_sheet_and_export_to_csv, and zipHolder
# should be provided in their respective modules and they should support async/await if used here.

@app.get("/api/csg_token")
async def get_csg_token():
    try:
        csg_token = mc.get('csg_token')
        if csg_token is None:
            raise HTTPException(status_code=404, detail="CSG token not found")
        return {'csg_token': csg_token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fetch_sheet")
async def fetch_sheet():
    try:
        result = fetch_sheet_and_export_to_csv()
        return {'result': result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/download_csv")
async def download_csv():
    try:
        # Assuming fetch_sheet_and_export_to_csv() generates "cat.csv"
        result = fetch_sheet_and_export_to_csv()
        return FileResponse(result, media_type="text/csv", filename="cat.csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
