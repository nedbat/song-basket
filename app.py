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
        value = self.r.get(key)
        if value is None:
            return default
        return pickle.loads(value)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.r.set(key, pickle.dumps(value))

    def pop(self, key, default=None):
        value = self.get(key, default)
        self.r.delete(key)
        return value


conf = tk.config_from_environment()
cred = tk.Credentials(*conf)
spotify = tk.Spotify()

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

def app_factory() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'aliens'

    @app.route('/', methods=['GET'])
    def main():
        user = session.get('user', None)
        if user is not None:
            token = users.get(user, None)
        else:
            token = None

        # Return early if no login or old session
        if user is None or token is None:
            session.pop('user', None)
            return 'You can <a href="/login">login</a>'

        if token.is_expiring:
            token = cred.refresh(token)
            users[user] = token

        with spotify.token_as(token):
            user = spotify.current_user()
        page = f"User: {user.display_name}. "
        page += f'<br>You can <a href="/logout">logout</a>'

        try:
            with spotify.token_as(token):
                playback = spotify.playback_currently_playing()

            item = playback.item.name if playback else None
            page += f'<br>Now playing: {item}'
        except tk.HTTPError:
            page += '<br>Error in retrieving now playing!'

        with spotify.token_as(token):
            playlists = spotify.playlists(user.id)
            page += f'<br>Playlists:<ul>'
            for pl in playlists.items:
                page += f'<li>{pl.name}</li>'
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

    return app


app = app_factory()

if __name__ == '__main__':
    app.run(threaded=True, port=5000)
