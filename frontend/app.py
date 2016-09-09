from datetime import datetime

from flask import Flask, render_template, abort
from flask.globals import request


STATE = None

app = Flask(__name__)


@app.route("/init/<int:max_balance>")
def init(max_balance):
    global STATE
    STATE = {
        'max_balance': max_balance,
        'balances': {
            'seller': 0,
            'buyer-credit': 0,
            'buyer-wallet': max_balance
        },
        'power': {
            'seller': 0,
            'buyer': 0
        },
        'log': []
    }
    return "OK"


@app.route("/")
@app.route("/<kind>")
def index(kind='seller'):
    if kind not in ('seller', 'buyer'):
        abort(404)
    if kind == 'seller':
        balance = STATE['balances']['seller']
        credit = STATE['balances']['buyer-credit']
    else:
        balance = STATE['balances']['buyer-wallet']
        credit = 0
    template = "index.html"
    if request.is_xhr:
        template = "inner.html"
    return render_template(
        template,
        kind=kind,
        balance=balance,
        credit=credit,
        max_balance=STATE['max_balance'],
        power=STATE['power'][kind],
        log=STATE['log']
    )


@app.route("/power_tick")
def power_tick():
    if STATE['balances']['buyer-credit'] > 0:
        STATE['power']['seller'] += 1
        STATE['power']['buyer'] += 1
        STATE['balances']['buyer-credit'] -= 1
        STATE['balances']['seller'] += 1
        return "OK"
    return "Not OK"


@app.route("/pay")
@app.route("/pay/<int:amount>")
def pay(amount=1):
    if STATE['balances']['buyer-wallet'] - amount >= 0:
        STATE['balances']['buyer-credit'] += amount
        STATE['balances']['buyer-wallet'] -= amount
        STATE['log'].append({'date': datetime.now(), 'amount': amount})
        return "OK"
    return "Not OK"


if __name__ == "__main__":
    init(100)
    app.run("0.0.0.0", 8000, debug=True)
