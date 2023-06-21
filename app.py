from flask import Flask, render_template, request
from pywebio.platform.flask import webio_view
import webbrowser, pywebio
from crawler import *

init_database()
app = Flask(__name__)
with open('sql/get_monthly_stats.sql', 'r') as f:
    get_monthly_stats = f.read()


def index():
    pywebio.output.put_markdown('# Warehouse Mobile Statistics')
    pywebio.output.put_markdown('[Back](/)')  # put_link function is inline
    form1 = pywebio.input.input_group('Username', [
        pywebio.input.input(
            'Phone number', type=pywebio.input.NUMBER, required=True, name='username', value='64',
            help_text='Input phone number carried by Warehouse in New Zealand. '
                      'DO NOT modify the country code. DO NOT contain the leading 0.'
        ),
        pywebio.input.checkbox(options=['Update data from Warehouse mobile website.'], name='update',
                               help_text='It will take time to retrieve data.'),
        pywebio.input.checkbox(options=['Recover incomplete recordings.'], name='recover',
                               help_text='It will clean records in the database and download again. If you interrupted'
                                         'the last download and have incomplete data now, please check this box.'
                               )
    ])
    username = str(form1['username'])
    update_data = form1['update']
    recover = form1['recover']

    if update_data:
        password = get_password_from_db(username)
        if not password:
            form2 = pywebio.input.input_group('Password', [
                pywebio.input.input('Password', name='password', type='password', required=True),
                pywebio.input.checkbox(options=['Remember password.'], name='remember_password'),
            ])
            password = form2['password']
            remember_password = form2['remember_password']
            if remember_password:
                save_password(username, password)
        pywebio.output.put_markdown('Logging in.')
        token = get_login_token(username, password)
        pywebio.output.put_markdown('Start to retrieve data.')
        if token:
            retrieve(username, token, recover)
        else:
            pywebio.output.put_text('The saved password in the database is expired (not correct).')
            delete_password(username)
            return
    pywebio.output.put_markdown(f'[View report](/report?username={username})')


@app.route('/report', methods=['GET'])
def report():
    username = request.args.get('username')
    c = sqlite3.connect(database_path)
    monthly_stats = pd.read_sql(con=c, sql=get_monthly_stats % username)
    c.close()
    return render_template(
        'report.html', username=username,
        month=monthly_stats['Month'].tolist(),
        data_usage=monthly_stats['Data (MB)'].tolist(),
        data_fee=monthly_stats['Data (NZD)'].tolist(),
        text_usage=monthly_stats['Text'].tolist(),
        text_fee=monthly_stats['Text (NZD)'].tolist(),
        call_usage=monthly_stats['Call (Minutes)'].tolist(),
        call_fee=monthly_stats['Call (NZD)'].tolist()
    )


app.add_url_rule(rule='/', endpoint='index', view_func=webio_view(index), methods=['GET', 'POST', 'OPTIONS'])

if __name__ == '__main__':
    webbrowser.open_new_tab('http://localhost:5000')
    app.run()
