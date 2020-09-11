# https://tekore.readthedocs.io/en/stable/reference/client.html#tekore.Spotify.playlist_items

import time

import tekore as tk


client_id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
client_secret = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

if 0:
    app_token = tk.request_client_token(client_id, client_secret)
    print(app_token)


try:
    with open("user_token.dat") as f:
        user_token = f.read()
except Exception:
    user_token = "nope"

while True:
    spotify = tk.Spotify(user_token)
    try:
        user = spotify.current_user()
    except Exception:
        user_token = tk.prompt_for_user_token(
            client_id,
            client_secret,
            "https://nedbatchelder.com/bogus/callback",
            scope=tk.scope.every
        )
        with open("user_token.dat", "w") as f:
            f.write(str(user_token))
    else:
        break

playlist_name = "Instrumental fns"

playlists = spotify.playlists(user.id)
playlist = next(p for p in playlists.items if p.name == playlist_name)

track_ids = set()
offset = 0
while offset < playlist.tracks.total:
    details = spotify.playlist_items(playlist.id, offset=offset)
    track_ids.update(track.track.id for track in details.items)
    offset += 100

print(len(track_ids), f"tracks in {playlist_name!r}")

track_id = None
while True:
    now_track = spotify.playback_currently_playing()
    if now_track is None:
        if track_id is not None:
            track_id = None
            print("Stopped")
    elif now_track.item.id != track_id:
        track_id = now_track.item.id
        is_in = "(already in playlist)" if track_id in track_ids else ""
        print(now_track.item.name, is_in)
    time.sleep(5)
