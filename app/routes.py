from app import app
from toolz.functoolz import pipe
from flask import request, url_for, jsonify
import json
import requests
from copy import copy
from datetime import datetime

from webargs import fields, validate
from webargs.flaskparser import use_args, use_kwargs

from app.funcs import getZips, load_response_all, cr
from app.presets import presets
from app.csg import filter_quote, format_rates


user_args = {
    'zip' : fields.Int(required=True),
    'county': fields.Str(),
    'age' : fields.Int(required=True, validate = lambda p: p >= 65),
    'gender' : fields.Str(required=True),
    'tobacco' : fields.Bool(required=True),
    'discounts' : fields.Bool(required=True),
    'date' : fields.Str(required=True),
    'plan' : fields.List(fields.Str(), required=True),
    'preset' : fields.Str(missing='top_ten'),
    'naic': fields.List(fields.Str(), required=False)
}

pdp_args = {
    "zip" : fields.Int(required=True),
    "year1" : fields.Int(missing=datetime.now().year, validate = lambda x: x >= datetime.now().year),
    "year2" : fields.Int(missing=datetime.now().year + 1, validate = lambda x: x >= datetime.now().year + 1)
}

@app.route('/api/counties', methods=['GET'])
def counties():
    zip5 = request.args.get('zip',None)

    if zip5:
        zips = getZips('static/uszips.csv')
        county_list = zips(zip5)
        return jsonify({'zip': county_list})

    return jsonify({'zip': None})

@app.route('/api/pdp', methods=['GET'])
@use_args(pdp_args, location= "query")
def pdp(args):
    try:
        year1 = args['year1']
        year2 = args['year2']
        zip5 = str(args['zip']).zfill(5)
        resp = cr.fetch_pdp(zip5, year1, year2)
        return {
            'body': resp,
            'error': None
        }
    except Exception as e:
        return {'body' : [None], 'error' : str(e)}


@app.route('/api/plans', methods=['GET'])
@use_args(user_args, location = "query")
# rewrite in async
def plans(args):
    qu = copy(args)

    def zip5_convert(a,b):
        x = qu.pop(a)
        qu[b] = str(x).zfill(5)

    def bool_int(a, new_field_name = None):
        b = qu.pop(a)
        if new_field_name:
            qu[new_field_name] = 0 if b == False else 1
        else:
            qu[a] = 0 if b == False else 1

    zip5_convert('zip', 'zip5')
    bool_int('discounts', 'apply_discounts')
    bool_int('tobacco')

    preset_name = qu.get('preset', None)
    if preset_name:
        qu.pop('preset')

    results = load_response_all(qu, verbose=True)
    #results['args'] = qu


    '''
    plans_ = qu.pop('plan')

    results = {}
    for p in ['N', 'F', 'G']:
        try:
            if p in plans_:
                qu['plan'] = p
                resp = cr.fetch_quote(**qu)
                results[p] = filter_quote(resp, verbose=True)
                #results[p] = load_response(cr, qu, naic=presets[preset_name], verbose=True)
        except Exception as e:
            results[p] = str(e)
    '''
    return jsonify(qu)



# Return validation errors as JSON
@app.errorhandler(422)
@app.errorhandler(400)
def handle_error(err):
    headers = err.data.get("headers", None)
    messages = err.data.get("messages", ["Invalid request."])
    if headers:
        return jsonify({"errors": messages}), err.code, headers
    else:
        return jsonify({"errors": messages}), err.code


'''
if __name__ == "__main__":
    app.run(debug=True)
'''
