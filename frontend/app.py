from datetime import datetime, timedelta

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
            'producer': 0,
            'consumer-credit': 0,
            'consumer-wallet': max_balance
        },
        'power': {
            'producer': 0,
            'consumer': 0
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
def index(kind='producer'):
    if kind not in ('producer', 'consumer'):
        abort(404)
    if kind == 'producer':
        balance = STATE['balances']['producer']
        credit = STATE['balances']['consumer-credit']
    else:
        balance = STATE['balances']['consumer-wallet']
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
        now=datetime.now(),
        threshold=timedelta(seconds=1)
    )


@app.route("/power_tick")
def power_tick():
    if STATE['balances']['consumer-credit'] > 0:
        STATE['power']['producer'] += STATE['per_tick']['power']
        STATE['power']['consumer'] += STATE['per_tick']['power']
        STATE['balances']['consumer-credit'] -= STATE['per_tick']['tokens']
        STATE['balances']['producer'] += STATE['per_tick']['tokens']
        return "OK"
    return "Not OK"


@app.route("/pay")
@app.route("/pay/<int:amount>")
def pay(amount=1):
    if STATE['balances']['consumer-wallet'] - amount >= 0:
        STATE['balances']['consumer-credit'] += amount
        STATE['balances']['consumer-wallet'] -= amount
        STATE['log'].append({'date': datetime.now(), 'amount': amount})
        return "OK"
    return "Not OK"


if __name__ == "__main__":
    init(100)
    app.run("0.0.0.0", 8000, debug=True)
