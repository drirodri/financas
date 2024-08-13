import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get stocks from symbols, sum up shares from equal symbols
    user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
    portfolios = db.execute("SELECT symbol, SUM(shares) as shares FROM portfolio WHERE id = ? GROUP BY symbol", session.get("user_id"))
    cash = user[0]['cash']

    # Create new pairs of key-value and save it in the stocks dict
    # Use the lookup function to fetch data from the api
    sum_value = 0
    for portfolio in portfolios:
        checkStock = lookup(portfolio['symbol'])
        portfolio['current_value'] = usd(checkStock['price'])
        portfolio['total_value'] = usd(portfolio['shares'] * checkStock['price'])
        sum_value += portfolio['shares'] * checkStock['price']

    total_sum = sum_value + cash

    return render_template("index.html", portfolios = portfolios, name = user[0]['name'], cash = usd(cash), sum_value = usd(sum_value), total_sum = usd(total_sum))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":

        user = (db.execute("SELECT cash, name FROM users WHERE id = ?", session.get("user_id")))
        wallet = usd(user[0]['cash'])
        name = user[0]['name']

        return render_template("buy.html", wallet = wallet, name = name)

    else:
        user = (db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id")))
        cash = user[0]['cash']
        shares = int(request.form.get("shares"))
        checkStock = lookup(request.form.get("symbol"))
        price = checkStock['price']
        symbol = checkStock['symbol']
        totalPrice = shares * price

        if not request.form.get("symbol"):
            return apology("Missing Stock symbol")

        if not shares:
            return apology("Missing amout of shares")

        if checkStock is None:
            return apology("Stock symbol does not exist")

        if shares < 1:
            return apology("Need to buy at least one share")

        if totalPrice > cash:
            return apology("Not enough cash in wallet")

        else:
            db.execute("INSERT INTO stocks (id, symbol, shares, price, action) VALUES (?, ?, ?, ?, ?)", session.get("user_id"), symbol, shares, price, "Bought")
            newWallet = cash - totalPrice
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newWallet, session.get("user_id"))
            db.execute("INSERT INTO portfolio (id, symbol, shares) VALUES (?, ?, ?)", session.get("user_id"), symbol, shares)
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
    stocks = db.execute("SELECT * FROM stocks WHERE id = ?", session.get("user_id"))
    cash = usd(user[0]['cash'])
    name = user[0]['name']

    for stock in stocks:
        stock['unit_value'] = stock['price']
        stock['unit_value'] = usd(stock['unit_value'])
        stock['stack_value'] = stock['price'] * stock['shares']
        stock['stack_value'] = usd(stock['stack_value'])

    return render_template("history.html", name = name, cash = cash, stocks = stocks )


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")

    # Method is POST
    else:
        # Get data from HTML form, search for quote Symbol in the API and save it to variable, 
        getQuote = request.form.get("quote")
        quote = lookup(getQuote)
        symbol = quote['symbol']
        price = usd(quote['price'])

        # The lookup function will return None if symbol is not found
        if quote is None:
            return apology("Stock symbol does not exist")

        name = db.execute("SELECT name FROM users WHERE id = ?", session.get("user_id"))
        return render_template("quoted.html", name=name[0]['name'], symbol = symbol, price = price)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Get values from html
        name = request.form.get("name")
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation= request.form.get("confirmation")

        # Check for erros
        if not name:
            return apology("Missing name")

        elif not username:
            return apology("Missing username")

        elif not password or not confirmation:
            return apology("Missing password")

        elif password != confirmation:
            return apology("Password don't match!")

        # Try to save values in database, if ValueError is returned, it means that the username is in use
        try:
            db.execute("INSERT INTO users (username, hash, name) VALUES (?, ?, ?)", username, generate_password_hash(password), name)

        except (ValueError):
            return apology("Username already in use", 200)

        # Log user in
        user_id = db.execute("SELECT id FROM users WHERE username = ?", username)
        session["user_id"] = user_id[0]['id']
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":

        # Pass into sell.html the symbols present in the database
        # to set the select form with only the symbols currently own
        user = db.execute("SELECT cash, name FROM users WHERE id = ?", session.get("user_id"))
        stock_symbols = db.execute("SELECT symbol FROM portfolio WHERE id = ?", session.get("user_id"))

        return render_template("sell.html", wallet = usd(user[0]['cash']), name = user[0]['name'], stock_symbols = stock_symbols)

    else:
        user = db.execute("SELECT * FROM users where id = ?", session.get("user_id"))
        stocks = db.execute("SELECT symbol, SUM(shares) as shares FROM portfolio WHERE id = ? GROUP BY symbol", session.get("user_id"))
        symbol = request.form.get("symbol")

        # Check for errors
        if not request.form.get("symbol"):
            return apology("Missing quote symbol")
        if not request.form.get("shares"):
            return apology("Missing shares")

        # Turn shares into int and create a flag variable
        shares = int(request.form.get("shares"))
        flag_stock = False;

        # Shares must be less or equal and the symbol must be equal
        for stock in stocks:
            if shares <= stock['shares'] and symbol == stock['symbol']:
                flag_stock = True

        # Check for errors using flag
        if flag_stock == False:
            return apology("Symbol not found")

        if flag_stock == False:
            return apology("You currently don't have the amount of shares selected")


        else:
            # Calculate the price using the api
            checkPrice = lookup(symbol)
            price = checkPrice['price']
            totalPrice = price * shares

            # Update cash and stocks history
            db.execute("INSERT INTO stocks (id, symbol, shares, price, action) VALUES (?, ?, ?, ?, ?)", session.get("user_id"), symbol, shares, price, "Sold")
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
            newWallet = cash[0]['cash'] + totalPrice

            # Update cash in users.db, update portfolio with new symbol/shares
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newWallet, session.get("user_id"))
            db.execute("UPDATE portfolio SET shares = shares - ? WHERE id = ? AND symbol = ?", shares, session.get("user_id"), symbol)

            # Delete form portfolio the symbols where value are less than or equal to 0
            db.execute("DELETE FROM portfolio WHERE shares <= 0 AND symbol = ? AND id = ?", symbol, session.get("user_id"))
            return redirect("/")

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():

    if request.method == "GET":
        return render_template("account.html")

    # method is POST
    else:
        checkPassword = db.execute("SELECT hash FROM users where id = ?", session.get("user_id"))
        password = request.form.get("password")
        new_password = request.form.get("new_password")
        new_confirmation = request.form.get("new_confirmation")

        # Check for errors
        if not password:
            return apology("Missing password")

        if not new_password:
            return apology("Missing new password")

        if not new_confirmation:
            return apology("Missing confirmation")

        if check_password_hash(checkPassword[0]['hash'], password) == False:
            return apology("Wrong password")

        if new_password == password:
            return apology("New and old password are equal")

        if new_password != new_confirmation:
            return apology("New password don't match")

        # Update db with new password hash
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_password), session.get("user_id"))
        return redirect("/")
