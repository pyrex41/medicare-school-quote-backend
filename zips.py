from csv import DictReader

class zipHolder():
    def __init__(self, file_name):
        self.load_zips(file_name)

    def __call__(self, zip5, show_state=False):
        county = self.lookup_county(zip5)
        if show_state:
            state = self.lookup_state(zip5)
            return county, state
        return county

    def lookup_county(self, zip5):
        return self.zip_counties.get(str(zip5).zfill(5), ['None'])
    
    def lookup_state(self, zip5):
        return self.zip_states.get(str(zip5).zfill(5), ['None'])

    def load_zips(self, file_name):
        zip_c = {}
        zip_s = {}
        with open(file_name, mode='r') as cf:
            cr = DictReader(cf)
            first_row = True
            for row in cr:
                if first_row:
                    first_row = False
                else:
                    zip_c[(row['zip'])] = [i.upper() for i in row['county_names_all'].split('|')]
                    zip_s[(row['zip'])] = row['state_id']
        self.zip_counties = zip_c
        self.zip_states = zip_s
