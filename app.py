"""Spoton playlist manager."""

import tekore as tk
from flask import Flask, request, redirect, session

cred = tk.Credentials(*tk.config_from_environment())

users = {}  # User tokens: state -> token (use state as a user ID)
current_playlist = None
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
app.config['SECRET_KEY'] = 'sP0t0N'

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

@app.route('/', methods=['GET'])
def main():
    uid, token = get_token()
    if token is None:
        return 'You can <a href="/login">login</a>'

    page = "<!DOCTYPE html><html><head>"
    page += "<meta http-equiv='refresh' content='5'>"
    page += "<style>.track { font-weight: bold; } .playlist { font-weight: bold; }</style>"
    page += "<body>"

    spotify = tk.Spotify(token)
    user = spotify.current_user()
    page += f"User: {user.display_name} (<a href='/logout'>logout</a>)"

    if current_playlist:
        page += f"<br>Playlist: <span class='playlist'>{current_playlist.name}</span>, {len(playlist_tracks)} tracks"

    try:
        playback = spotify.playback_currently_playing()
        if playback:
            item = playback.item
            page += f"<br>Playing: <span class='track'>{item.name}</span>"
            if item.id in playlist_tracks:
                page += f' (in playlist. <a href="/rmfromlist?id={item.id}">Remove</a>)'
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
    users[state] = token
    return redirect('/', 307)

@app.route('/logout', methods=['GET'])
def logout():
    uid = session.pop('user', None)
    if uid is not None:
        users.pop(uid, None)
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
    global current_playlist, playlist_tracks
    uid, token = get_token()
    spotify = tk.Spotify(token)
    plid = request.args.get('id')
    current_playlist = spotify.playlist(plid)
    playlist_tracks = playlist_tracks(spotify, current_playlist)
    return redirect('/', 307)
    
@app.route('/addtolist', methods=['GET'])
def add_to_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_id = request.args.get('id')
    track = spotify.track(track_id)
    spotify.playlist_add(current_playlist.id, [track.uri])
    playlist_tracks.add(track_id)
    return redirect('/', 307)

@app.route('/rmfromlist', methods=['GET'])
def rm_from_list():
    uid, token = get_token()
    spotify = tk.Spotify(token)
    track_id = request.args.get('id')
    track = spotify.track(track_id)
    spotify.playlist_remove(current_playlist.id, [track.uri])
    playlist_tracks.remove(track_id)
    spotify.playback_next()
    return redirect('/', 307)

if __name__ == '__main__':
    app.run(threaded=True, port=5000)
