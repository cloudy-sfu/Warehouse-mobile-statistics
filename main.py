from get_data import get_data
from get_stats import statistics
import pywebio
import sys
import os


def close_program():
    pywebio.session.eval_js('window.close();')


def clear_cache():
    username = pywebio.input.select(
        label='Cache file', required=True,
        options=[(x, x) for x in os.listdir('raw/')],
        help_text='Choose the cache file containing your phone number.'
    )
    os.remove(os.path.join('raw/', username))


def index():
    session = pywebio.session.get_current_session()
    session.defer_call(lambda: sys.exit(0))
    pywebio.output.clear()

    pywebio.output.put_markdown('# Warehouse Mobile Statistics')
    pywebio.output.put_row([
        pywebio.output.put_button(label='Home', color='primary', onclick=index),
        pywebio.output.put_button(label='Clear cache', color='dark text-nowrap', onclick=clear_cache),
        pywebio.output.put_button(label='Close', color='danger', onclick=close_program),
    ], size='auto auto 100%; column-gap: 0.5em;')
    username = pywebio.input.input(
        'NZ phone number', type=pywebio.input.NUMBER, required=True,
        help_text='DO NOT contain any blanks, dashes, brackets, "+64" prefix or other not-numbers.'
    )
    username = '64' + str(username)
    retrieve_data = pywebio.input.select(
        'Update data?', options=[('Yes', True), ('No', False)],
        help_text='If you choose \'Yes\', this program will request data from warehouse mobile website.'
    )
    if retrieve_data:
        password = pywebio.input.input(
            'Password', type='password', required=True,
            help_text='We do not preserve/save/cache your password.'
        )
        try:
            pywebio.output.put_text('Retrieving data from warehouse mobile website. It may takes some minutes, and '
                                    'please do not close this program.')
            get_data(username, password)
        except Exception as e:
            pywebio.output.put_error(e)
            return
    try:
        s = statistics(username)
    except Exception as e:
        pywebio.output.put_error(e)
        return
    pywebio.output.put_grid([
        [pywebio.output.span(pywebio.output.put_markdown('## This month'), col=3)],
        [pywebio.output.put_html(
            "<div class='alert alert-light border-dark m-2 text-dark'><p>Data usage</p> "
            f"<h3 class='text-center'>{s['tmu']['d']}</h3> <p class='text-right'>(MB) $ {s['tmf']['d']}</p></div>"
        ), pywebio.output.put_html(
            "<div class='alert alert-light border-dark m-2 text-dark'><p>Text usage</p> "
            f"<h3 class='text-center'>{s['tmu']['t']}</h3> <p class='text-right'>$ {s['tmf']['t']} </p></div>"
        ), pywebio.output.put_html(
            "<div class='alert alert-light border-dark m-2 text-dark'><p>Call usage</p> "
            f"<h3 class='text-center'>{s['tmu']['c']}</h3> <p class='text-right'>(Minutes) $ {s['tmf']['c']}</p></div>"
        )]
    ])
    pywebio.output.put_markdown('## History')
    pywebio.output.put_text('Usage and extra fee not covered by value packs.')
    pywebio.output.put_html(s['hu'].to_html(border=0))


if __name__ == '__main__':
    # Debug
    # pywebio.start_server([index], auto_open_webbrowser=False, port=5000, debug=True)
    # Deploy
    pywebio.start_server([index], auto_open_webbrowser=True)
