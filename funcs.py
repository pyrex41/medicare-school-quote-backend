from copy import copy
from babel.numbers import format_currency as format_currency_verbose
from datetime import datetime
from toolz.functoolz import pipe

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

def format_results(results):
    row_dict = {}
    for r in results:
        for ol in r:
            company = ol['company']
            row = row_dict.get(company, {})
            row[ol['plan']] = ol['rate']
            row['naic'] = ol['naic']
            row_dict[company] = row

    rows = []
    for c,d in row_dict.items():
        row = {'company': c}
        row['F Rate'] = d.get('F', None)
        row['G Rate'] = d.get('G', None)
        row['N Rate'] = d.get('N', None)
        row['naic'] = int(d.get('naic', None))
        rows.append(row)
    return rows

def filter_quote(quote_resp, household = False, custom_naic=None, select=False):
        fresp = list(filter(lambda x: x['select'] == False, quote_resp)) if not select else quote_resp

        if custom_naic:
            return pipe(
                    list(filter(lambda x: int(x['company_base']['naic']) in custom_naic,fresp)),
                    format_rates)
        else:
            return format_rates(fresp, household = household)

def format_pdp(pdp_results, *_years):
    out = []
    years = list(_years)
    if len(years) == 0:
        years.append(datetime.today().year)
    for pdpr in pdp_results:
        dt_format = "%Y-%m-%dT%H:%M:%SZ"
        st_dt = pdpr['effective_date']
        dt = datetime.strptime(st_dt, dt_format)
        info = {
            'Plan Name': pdpr['plan_name'],
            'Plan Type': pdpr['plan_type'],
            'State': pdpr['state'],
            'rate': format_currency(pdpr['month_rate']/100),
            'year': dt.year
        }
        out.append(info)
    fout = filter(lambda x: x['year'] in years, out)
    return list(fout)

def load_response_all(cr, query_data, verbose=True):
    results = []
    plans_ = query_data.pop('plan')
    for p in ['N', 'F', 'G']:
        qu = copy(query_data)
        if p in plans_:
            qu['plan'] = p
            results.append(cr.load_response(qu))

    return format_results(results)