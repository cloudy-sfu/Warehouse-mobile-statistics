select strftime('%%Y-%%m', date_and_time) as Month,
       sum(charged_units * iif(charge_type IN ('International call (call specific destinations)', 'NZ Call'), 1, 0)) as 'Call (Minutes)',
       round(sum(amount * iif(charge_type IN ('International call (call specific destinations)', 'NZ Call'), 1, 0)), 2) as 'Call (NZD)',
       round(sum(charged_units * iif(charge_type = 'Data', 1, 0)), 2) as 'Data (MB)',
       round(sum(amount * iif(charge_type = 'Data', 1, 0)), 2) as 'Data (NZD)',
       sum(charged_units * iif(charge_type IN ('International Text (other than OZ)', 'NZ Text'), 1, 0)) as 'Text',
       round(sum(amount * iif(charge_type IN ('International Text (other than OZ)', 'NZ Text'), 1, 0)), 2) as 'Text (NZD)'
from "%s"
group by Month;
