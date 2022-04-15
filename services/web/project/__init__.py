# https://testdriven.io/blog/dockerizing-flask-with-postgres-gunicorn-and-nginx/#gunicorn
import json
import os

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
import datetime
from typing import List, Optional, Set
from plexapi.myplex import *
from plexapi.video import Episode, Show, Season, Video
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config.from_object("project.config.Config")
db = SQLAlchemy(app)

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(lambda: get_optimize_on_deck(), 'cron', hour=3)
scheduler.start()


class OptimizationStatus(Enum):
    NOT_OPTIMIZED = "NOT_OPTIMIZED"
    PENDING = "PENDING"
    OPTIMIZED = "OPTIMIZED"


class Optimization(db.Model):
    __tablename__ = "optimizations"

    key = db.Column(db.String(128), primary_key=True)
    optimize_status = db.Column(db.String(50), default=OptimizationStatus.NOT_OPTIMIZED.name, nullable=False)
    timestamp = db.Column(db.DateTime(), default=datetime.datetime.now(), nullable=False)

    def __init__(self, key, optimize_status: OptimizationStatus):
        self.key = key
        self.optimize_status = optimize_status.name


def connect_plex(username: str, password: str) -> PlexServer:
    account: MyPlexAccount = MyPlexAccount(username, password)
    plex: PlexServer = account.resource('EA-NAS').connect()
    return plex


def get_next_ep(episode: Episode) -> Optional[Episode]:
    season_eps: List[Episode] = episode.season().episodes()
    index = season_eps.index(episode)
    if index < len(season_eps) - 1:
        return season_eps[index + 1]

    season: Season = episode.season()
    show: Show = episode.show()
    show_seasons: List[Season] = show.seasons()
    index = show_seasons.index(season)
    if index < len(show_seasons) - 1:
        next_season: Season = show_seasons[index + 1]
        return next_season.episodes()[0]

    return None


def find_on_deck(plex: PlexServer) -> Set[Video]:
    account_names: List[str] = list(map(lambda plex_account: plex_account.name, plex.systemAccounts()))
    media_to_optimize: Set = set()
    for item in plex.library.onDeck():
        media_to_optimize.add(item)
        # if item is an Episode, add the next ep as well if exists
        if isinstance(item, Episode):
            next_ep: Optional[Episode] = get_next_ep(item)
            if next_ep is not None:
                media_to_optimize.add(next_ep)

    for account_name in account_names:
        try:
            for item in plex.switchUser(account_name).library.onDeck():
                media_to_optimize.add(item)
                # if item is an Episode, add the next ep as well if exists
                if isinstance(item, Episode):
                    next_ep: Optional[Episode] = get_next_ep(item)
                    if next_ep is not None:
                        media_to_optimize.add(next_ep)
        except:
            continue

    return media_to_optimize


def update_optimization_table(new_row: Optimization):
    old_row = Optimization.query.get(new_row.key)
    if old_row is None:
        db.session.add(new_row)
    else:
        old_row.optimize_status = new_row.optimize_status
        old_row.timestamp = datetime.datetime.now()
    db.session.commit()


def optimize_on_deck(plex_username: str, plex_password: str):
    # get account names connected to server to pull their on deck
    plex = connect_plex(plex_username, plex_password)
    on_deck: Set[Video] = find_on_deck(plex)
    already_optimized: List[Video] = list(map(lambda x: x.items()[0], plex.optimizedItems()))

    for media in on_deck:
        if media not in already_optimized:
            media.optimize(targetTagID=3)
            update_optimization_table(Optimization(media.key, OptimizationStatus.PENDING))

    # TODO: Check DB for optimized that are not on deck, delete those


@app.route("/")
def hello_world():
    return jsonify(hello="world")


@app.route("/optimize/ondeck")
def get_optimize_on_deck():
    try:
        f = open('/config/secrets.json')
    except:
        return jsonify(error="Please mount dir to /config and load a secrets.json")

    secrets = json.load(f)
    if "PLEX_USERNAME" not in secrets.keys():
        return jsonify(error="PLEX_USERNAME not found in secrets.json")
    if "PLEX_PASSWORD" not in secrets.keys():
        return jsonify(error="PLEX_PASSWORD not found in secrets.json")

    optimize_on_deck(secrets["PLEX_USERNAME"], secrets["PLEX_PASSWORD"])
    return jsonify(success="test")
