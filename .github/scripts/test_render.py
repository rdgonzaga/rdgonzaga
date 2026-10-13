import unittest
from datetime import datetime, timedelta, timezone

import render

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
INFO = {"user": {"playcount": "111507"}}


def track(name="Better Together", artist="Jack Johnson", album="In Between Dreams",
          art="https://lastfm.freetls.fastly.net/i/u/300x300/abc.jpg", uts=None, playing=False):
    t = {"name": name, "artist": {"#text": artist}, "album": {"#text": album},
         "image": [{"size": "small", "#text": "s.jpg"}, {"size": "extralarge", "#text": art}]}
    if playing:
        t["@attr"] = {"nowplaying": "true"}
    else:
        t["date"] = {"uts": str(uts or int((NOW - timedelta(hours=11)).timestamp()))}
    return t


class Helpers(unittest.TestCase):
    def test_ago(self):
        self.assertEqual(render.ago(timedelta(seconds=30)), "just now")
        self.assertEqual(render.ago(timedelta(minutes=12)), "12m ago")
        self.assertEqual(render.ago(timedelta(hours=3, minutes=59)), "3h ago")
        self.assertEqual(render.ago(timedelta(days=2, hours=5)), "2d ago")

    def test_clip(self):
        self.assertEqual(render.clip("short", 10), "short")
        self.assertEqual(render.clip("exactly10!", 10), "exactly10!")
        self.assertEqual(render.clip("a very long title", 8), "a very…")


class Parse(unittest.TestCase):
    def test_last_played(self):
        m = render.parse_music({"recenttracks": {"track": [track()]}}, INFO, NOW)
        self.assertEqual(m["track"], "Better Together")
        self.assertEqual(m["artist"], "Jack Johnson")
        self.assertEqual(m["album"], "In Between Dreams")
        self.assertFalse(m["playing"])
        self.assertEqual(m["ago"], "11h ago")
        self.assertEqual(m["scrobbles"], 111507)
        self.assertTrue(m["art"].endswith("abc.jpg"))

    def test_now_playing_takes_first_of_two(self):
        recent = {"recenttracks": {"track": [track(name="Live One", playing=True), track()]}}
        m = render.parse_music(recent, INFO, NOW)
        self.assertEqual(m["track"], "Live One")
        self.assertTrue(m["playing"])
        self.assertIsNone(m["ago"])

    def test_single_track_as_dict(self):
        m = render.parse_music({"recenttracks": {"track": track()}}, INFO, NOW)
        self.assertEqual(m["track"], "Better Together")

    def test_placeholder_and_missing_art(self):
        ph = "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png"
        self.assertIsNone(render.parse_music({"recenttracks": {"track": [track(art=ph)]}}, INFO, NOW)["art"])
        self.assertIsNone(render.parse_music({"recenttracks": {"track": [track(art="")]}}, INFO, NOW)["art"])

    def test_no_tracks(self):
        self.assertIsNone(render.parse_music({"recenttracks": {"track": []}}, INFO, NOW))


if __name__ == "__main__":
    unittest.main()
