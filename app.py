from flask import Flask, render_template
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

# connect scraper
from scraper_module import run_scraper

@app.route("/scrape")
def scrape():
    data = run_scraper()
    return render_template("results.html", data=data)
