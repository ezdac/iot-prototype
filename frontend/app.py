from datetime import datetime

from flask import Flask, render_template, abort
from flask.globals import request


STATE = None

app = Flask(__name__)


@app.route("/init")
@app.route("/init/<int:max_balance>")
@app.route("/init/<int:max_balance>/<float:power_per_tick>/<float:tokens_per_tick>")
def init(max_balance=100, power_per_tick=0.5, tokens_per_tick=1.0):
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
        'per_tick': {
            'tokens': tokens_per_tick,
            'power': power_per_tick
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
        log=list(reversed(STATE['log']))[:10],
    )


@app.route("/power_tick")
def power_tick():
    if STATE['balances']['buyer-credit'] > 0:
        STATE['power']['seller'] += STATE['per_tick']['power']
        STATE['power']['buyer'] += STATE['per_tick']['power']
        STATE['balances']['buyer-credit'] -= STATE['per_tick']['tokens']
        STATE['balances']['seller'] += STATE['per_tick']['tokens']
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
