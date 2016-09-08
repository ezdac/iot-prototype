# Requirements

* `flask`

# Usage

Start the server with `python app.py` it will listen on `0.0.0.0:8000`.

# Endpoints

* `/init/<amount>`

  Resets all internal state and initializes the buyers wallet to `<amount>`

* `/seller`

  Show the sellers view

* `/buyer`

  Show the buyers view

* `/pay/<amount>` or just `/pay`

  Transfer `<amount>` (or 1 if missing) tokens from buyer's wallet to buyer's credit with seller

* `/power_tick`

  Record a tick of power transfer from seller to buyer

