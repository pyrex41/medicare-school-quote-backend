from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from datetime import datetime
from csg import csgRequest
from zips import zipHolder
from config import Config

from webargs import fields
from webargs.flaskparser import parser

api_key = Config.API_KEY
cr = csgRequest(api_key)

app = Flask(__name__)
api = Api(app)

# zip code
zip_args = {
    'zip5': fields.Int(required=True, validate = lambda i: len(str(i)) == 5)
}
class Zip(Resource):
    def __init__(self):
        self.zips = zipHolder('static/uszips.csv')
    def get(self):
        args = parser.parse(zip_args, request, location="query")
        zip5 = args.get('zip5', None)
        county_list = self.zips(zip5)
        return jsonify(county_list)
api.add_resource(Zip, '/api/counties')


# pdp get
pdp_args = {
    "zip" : fields.Int(required=True),
    "year1" : fields.Int(missing=datetime.now().year, validate = lambda x: x >= datetime.now().year),
    "year2" : fields.Int(missing=datetime.now().year + 1, validate = lambda x: x >= datetime.now().year + 1)
}

class PDP(Resource):
    def get(self):
        args = parser.parse(pdp_args,request, location="query")
        return jsonify(args)

api.add_resource(PDP, '/api/pdp')

# plans
user_args = {
    'zip' : fields.Int(required=True),
    'county': fields.Str(),
    'age' : fields.Int(required=True, validate = lambda p: p >= 65),
    'gender' : fields.Str(required=True),
    'tobacco' : fields.Bool(required=True),
    'discounts' : fields.Bool(required=True),
    'date' : fields.Str(required=True),
    'plan' : fields.List(fields.Str(), required=True),
    'naic': fields.List(fields.Str(), required=False)
}
class Plans(Resource):
    def __init__(self):
        self.api_key = api_key
        self.cr = cr

    def get(self):
        args = parser.parse(user_args, request, location="query")
        args = self.custom_arg_transform(args)
        results = self.cr.load_response_all(args)
        return jsonify(results)

    def custom_arg_transform(self, args):
        args['zip5'] = str(args.pop('zip')).zfill(5)
        args['effective_date'] = args.pop('date')
        
        # inline helper function to update field names
        def bool_int(a, new_field_name = None):
            b = args.pop(a)
            if new_field_name:
                args[new_field_name] = 0 if b == False else 1
            else:
                args[a] = 0 if b == False else 1
        
        bool_int('discounts', 'apply_discounts')
        bool_int('tobacco')
        return args

api.add_resource(Plans, '/api/plans')

if __name__ == '__main__':
    app.run(debug=True)