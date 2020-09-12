import itertools
import os
import pickle

import redis
import tekore as tk
from flask import Flask, request, redirect, session

class RedisDict:
    db_nums = itertools.count()

    def __init__(self):
        self.r = redis.from_url(os.environ.get("REDIS_URL"), db=next(self.db_nums))

    def get(self, key, default=None):
        value = self.r.get(pickle.dumps(key))
        if value is None:
            return default
        return pickle.loads(value)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.r.set(pickle.dumps(key), pickle.dumps(value))

    def pop(self, key, default=None):
        value = self.get(key, default)
        self.r.delete(pickle.dumps(key))
        return value


cred = tk.Credentials(*tk.config_from_environment())

users = RedisDict()     # User tokens: state -> token (use state as a user ID)


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
app.config['SECRET_KEY'] = 'aliens'

def get_token():
    uid = session.get('user', None)
    if uid is not None:
        token = users.get((uid, "token"), None)
    else:
        token = None

    # Return early if no login or old session
    if uid is None or token is None:
        session.pop('user', None)
        return None, None

    if token.is_expiring:
        token = cred.refresh(token)
        users[uid, "token"] = token

    return uid, token

@app.route('/', methods=['GET'])
def main():
    uid, token = get_token()
    if token is None:
        return 'You can <a href="/login">login</a>'

    page = "<!DOCTYPE html><html><head>"
    page += "<meta http-equiv='refresh' content='5'>"
    page += "<body>"

    spotify = tk.Spotify(token)
    user = spotify.current_user()
    page += f"User: {user.display_name} (<a href='/logout'>logout</a>)"

    plid, pl_name, tracks = users.get((uid, "playlist"), (None, "", set()))
    if plid:
        page += f"<br>Playlist: {pl_name}, {len(tracks)} tracks"

    try:
        playback = spotify.playback_currently_playing()
        if playback:
            item = playback.item
            page += f'<br>Now playing: {item.name} '
            if item.id in tracks:
                page += f' (in playlist. <a href="/rmfromlist?id={item.id}">Remove from playlist</a>)'
            else:
                page += f' (<a href="/addtolist?id={item.id}">Add to playlist</a>)'
        else:
            page += f'<br>Nothing playing'
    except tk.HTTPError:
        page += '<br>Error in retrieving now playing!'

    playlists = spotify.playlists(user.id)
    page += f'<br>Playlists:<ul>'
    for pl in playlists.items:
        page += f'<li><a href="/setplaylist?id={pl.id}">{pl.name}</a></li>'
    page += '</ul>'

    return page

@app.route('/login', methods=['GET'])
def login():
    if 'user' in session:
        return redirect('/', 307)

    auth = tk.UserAuth(cred, SCOPE)
    return redirect(auth.url, 307)

@app.route('/callback', methods=['GET'])
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
    users[state, "token"] = token
    return redirect('/', 307)

@app.route('/logout', methods=['GET'])
def logout():
    uid = session.pop('user', None)
    if uid is not None:
        users.pop((uid, "token"), None)
    return redirect('/', 307)

def playlist_tracks(spotify, playlist):
    track_ids = set()
    offset = 0
    while offset < playlist.tracks.total:
        details = spotify.playlist_items(playlist.id, offset=offset)
        track_ids.update(track.track.id for track in details.items)
        offset += 100
    return track_ids


@app.route('/setplaylist', methods=['GET'])
def set_playlist():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    plid = request.args.get('id')
    playlist = spotify.playlist(plid)
    tracks = playlist_tracks(spotify, playlist)
    print(f"With {len(tracks)} tracks")
    users[uid, "playlist"] = (plid, playlist.name, tracks)
    return redirect('/', 307)
    
@app.route('/addtolist', methods=['GET'])
def add_to_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_id = request.args.get('id')
    track = spotify.track(track_id)
    plid, pl_name, tracks = users.get((uid, "playlist"), (None, "", set()))
    spotify.playlist_add(plid, [track.uri])
    tracks.add(track_id)
    users[uid, "playlist"] = (plid, pl_name, tracks)
    return redirect('/', 307)

@app.route('/rmfromlist', methods=['GET'])
def rm_from_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_id = request.args.get('id')
    track = spotify.track(track_id)
    plid, pl_name, tracks = users.get((uid, "playlist"), (None, "", set()))
    spotify.playlist_remove(plid, [track.uri])
    tracks.remove(track_id)
    users[uid, "playlist"] = (plid, pl_name, tracks)
    return redirect('/', 307)

if __name__ == '__main__':
    app.run(threaded=True, port=5000)
