import os
import pandas as pd


def statistics(username):
    raw_usage_path = f'raw/{username}.pkl'
    if not os.path.exists(raw_usage_path):
        raise Exception(f'Records does not exist. Requested path is {raw_usage_path}')
    raw_usage = pd.read_pickle(raw_usage_path)
    if raw_usage.shape[0] == 0:
        raise Exception(f'Records are empty. Requested path is {raw_usage_path}')
    monthly_group_by = raw_usage.groupby(pd.Grouper(key='date_and_time', freq='M'))

    monthly_usage = pd.DataFrame({
        'Data (MB)': monthly_group_by.apply(lambda x: x.loc[
            x['charge_type'] == 'Data', 'charged_units'
        ].sum().round(2)),
        'Text': monthly_group_by.apply(lambda x: x.loc[
            (x['charge_type'] == 'International Text (other than OZ)') |
            (x['charge_type'] == 'NZ Text'), 'charged_units'
        ].sum().astype(int)),
        'Call (Minutes)': monthly_group_by.apply(lambda x: x.loc[
            (x['charge_type'] == 'NZ Call') |
            (x['charge_type'] == 'International call (call specific destinations)'), 'charged_units'
        ].sum().astype(int)),
        'Data fee (NZD)': monthly_group_by.apply(lambda x: x.loc[x['charge_type'] == 'Data', 'amount'].sum()),
        'Text fee (NZD)': monthly_group_by.apply(lambda x: x.loc[
            (x['charge_type'] == 'International Text (other than OZ)') |
            (x['charge_type'] == 'NZ Text'), 'amount'
        ].sum()),
        'Call fee (NZD)': monthly_group_by.apply(lambda x: x.loc[
            (x['charge_type'] == 'NZ Call') |
            (x['charge_type'] == 'International call (call specific destinations)'), 'amount'
        ].sum()),
    }).sort_index(ascending=False)
    this_month = raw_usage['date_and_time'].max()
    this_month_usage = monthly_usage.loc[
        (monthly_usage.index.year == this_month.year) &
        (monthly_usage.index.month == this_month.month), :
    ]
    monthly_usage.set_index(monthly_usage.index.strftime('%Y-%m'), inplace=True)
    monthly_usage.index.name = None
    return {
        'tmu': {
            'd': float(this_month_usage['Data (MB)']),
            't': int(this_month_usage['Text']),
            'c': int(this_month_usage['Call (Minutes)'])
        },
        'tmf': {
            'd': float(this_month_usage['Data fee (NZD)']),
            't': float(this_month_usage['Text fee (NZD)']),
            'c': float(this_month_usage['Call fee (NZD)'])
        },
        'hu': monthly_usage,
    }
