from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restful import Resource, Api
from datetime import datetime
from csg import csgRequest, fetch_sheet_and_export_to_csv, csv_to_dict
from zips import zipHolder
from config import Config

from webargs import fields
from webargs.flaskparser import parser

api_key = Config.API_KEY
cr = csgRequest(api_key)

app = Flask(__name__)
CORS(app, resources=r'/api/*')
api = Api(app)

# zip code
zip_args = {
    'zip': fields.Int(required=True)
}
class Zip(Resource):
    def __init__(self):
        self.zips = zipHolder('static/uszips.csv')
    def get(self):
        args = parser.parse(zip_args, request, location="query")
        zip5 = args.get('zip', None)
        county_list = self.zips(zip5) if zip5 else None
        county_dict = { 'zip' : county_list }
        return jsonify(county_dict)
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

class FetchSheet(Resource):
    def get(self):
        fetch_sheet_and_export_to_csv()
        return jsonify({'message': 'Sheet fetched and exported to CSV'})

api.add_resource(FetchSheet, '/api/fetch_sheet')

from flask import send_file

class DownloadCSV(Resource):
    def get(self):
        return send_file('cat.csv', mimetype='text/csv', as_attachment=True, attachment_filename='cat.csv')

api.add_resource(DownloadCSV, '/api/download_csv')




if __name__ == '__main__':
    app.run(debug=True)
