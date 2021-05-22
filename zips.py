from csv import DictReader

class zipHolder():
    def __init__(self, file_name):
        self.load_zips(file_name)

    def __call__(self, zip5):
        return self.lookup_zip(zip5)

    def lookup_zip(self, zip5):
        return self.zips.get(str(zip5), ['None'])

    def load_zips(self, file_name):
        zips = {}
        with open(file_name, mode='r') as cf:
            cr = DictReader(cf)
            first_row = True
            for row in cr:
                if first_row:
                    first_row = False
                else:
                    zips[(row['zip'])] = [i.upper() for i in row['county_names_all'].split('|')]
        self.zips = zips