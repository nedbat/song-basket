"""Songbasket playlist manager."""

import collections
import os

import dotenv
import tekore as tk
from flask import Flask, request, redirect, session

dotenv.load_dotenv()
cred = tk.Credentials(*tk.config_from_environment())

# User tokens: state -> token (use state as a user ID)
users = {}

# A Tekore Playlist object.
current_playlist = None

# The set of the playlists's track uri's.
playlist_tracks = None

SCOPE = (
    tk.scope.playlist_modify_private +
    tk.scope.playlist_modify_public +
    tk.scope.playlist_read_collaborative +
    tk.scope.playlist_read_private +
    tk.scope.user_modify_playback_state +
    tk.scope.user_read_currently_playing +
    tk.scope.user_read_playback_position +
    tk.scope.user_read_playback_state
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

def get_token():
    uid = session.get('user', None)
    if uid is not None:
        token = users.get(uid, None)
    else:
        token = None

    # Return early if no login or old session
    if uid is None or token is None:
        session.pop('user', None)
        return None, None

    if token.is_expiring:
        token = cred.refresh(token)
        users[uid] = token

    return uid, token

@app.route('/')
def main():
    page = "<!DOCTYPE html><html><head>"
    page += "<title>Song Basket</title>"

    uid, token = get_token()
    if token is None:
        page += "<body>[<a href='/login'>Login</a>]"
        return page

    page += "<meta http-equiv='refresh' content='5'>"
    page += "<style>.track { font-weight: bold; } .playlist { font-weight: bold; }</style>"
    page += "<body>"

    spotify = tk.Spotify(token)
    user = spotify.current_user()
    page += f"User: {user.display_name} [<a href='/logout'>Logout</a>]"

    if current_playlist:
        page += f"<br>Playlist: <span class='playlist'>{current_playlist.name}</span>, {len(playlist_tracks)} tracks"
        page += " [<a href='/playlists'>Change</a>]"
    else:
        page += f"<br>No playlist [<a href='/playlists'>Choose one</a>]"

    try:
        playback = spotify.playback_currently_playing()
        if playback:
            item = playback.item
            if item is not None:
                page += f"<br>Playing: <span class='track'>{item.name}</span>"
                if playlist_tracks:
                    if item.uri in playlist_tracks:
                        page += f' in playlist. [<a href="/rmfromlist?uri={item.uri}">Remove</a>]'
                    else:
                        page += f''' [
                            <a href="/addtolist?uri={item.uri}">Add to playlist</a>
                            <a href="/addtolist?uri={item.uri}&next=1">and next</a>
                            ]'''
            else:
                page += "<br>Playing, but nothing?"
        else:
            page += "<br>Nothing playing"
    except tk.HTTPError:
        page += "<br>Error in retrieving now playing!"

    return page

@app.route('/playlists')
def playlists():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    user = spotify.current_user()
    playlists = spotify.playlists(user.id)
    page = "<br>Playlists:<ul>"
    for pl in playlists.items:
        page += f"<li><a href='/setplaylist?id={pl.id}'>{pl.name}</a></li>"
    page += "</ul>"
    return page

@app.route('/login')
def login():
    if 'user' in session:
        return redirect('/', 307)

    auth = tk.UserAuth(cred, SCOPE)
    return redirect(auth.url, 307)

@app.route('/callback')
def login_callback():
    code = request.args.get('code', None)
    state = request.args.get('state', None)
    # This seems like the wrong way to make this work, but it works.
    auth = tk.UserAuth(cred, SCOPE)
    auth.state = state

    if auth is None:
        return 'Invalid state!', 400

    token = auth.request_token(code, state)
    session['user'] = state
    users[state] = token
    return redirect('/', 307)

@app.route('/logout')
def logout():
    uid = session.pop('user', None)
    if uid is not None:
        users.pop(uid, None)
    return redirect('/', 307)

def get_playlist_tracks(spotify, playlist):
    track_count = collections.Counter()
    track_uris = set()
    offset = 0
    while offset < playlist.tracks.total:
        details = spotify.playlist_items(playlist.id, offset=offset)
        track_uris.update(track.track.uri for track in details.items)
        track_count.update(track.track.id for track in details.items)
        offset += 100
    for id, count in track_count.items():
        if count > 1:
            track = spotify.track(id)
            print(f"Duplicate! {track!r}")
    return track_uris


@app.route('/setplaylist')
def set_playlist():
    global current_playlist, playlist_tracks
    uid, token = get_token()
    spotify = tk.Spotify(token)
    plid = request.args.get('id')
    current_playlist = spotify.playlist(plid)
    playlist_tracks = get_playlist_tracks(spotify, current_playlist)
    return redirect('/', 307)
    
@app.route('/addtolist')
def add_to_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_uri = request.args.get('uri')
    spotify.playlist_add(current_playlist.id, [track_uri])
    playlist_tracks.add(track_uri)
    if int(request.args.get('next', '0')):
        spotify.playback_next()
    return redirect('/', 307)

@app.route('/rmfromlist')
def rm_from_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_uri = request.args.get('uri')
    spotify.playlist_remove(current_playlist.id, [track_uri])
    playlist_tracks.remove(track_uri)
    spotify.playback_next()
    return redirect('/', 307)

if __name__ == '__main__':
    app.run(threaded=True, port=5000)
