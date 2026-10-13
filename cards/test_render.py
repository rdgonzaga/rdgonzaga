import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = render.ASSETS
        render.ASSETS = Path(self.tmp.name)

    def tearDown(self):
        render.ASSETS = self.old
        self.tmp.cleanup()

    def svg(self, **kw):
        m = {"track": "Better Together", "artist": "Jack Johnson", "album": "In Between Dreams",
             "playing": False, "ago": "11h ago", "scrobbles": 111507, "art": None,
             "top": [("She & Him", 42), ("Clairo", 31), ("Men I Trust", 18)]}
        m.update(kw)
        render.render_music(m)
        return (render.ASSETS / "music.svg").read_text(encoding="utf-8")

    def test_last_played(self):
        s = self.svg()
        self.assertIn(" last played ", s)
        self.assertIn("11h ago", s)
        self.assertIn("111,507 scrobbles", s)
        self.assertIn("# in between dreams", s)
        self.assertIn("♪", s)  # no art -> placeholder
        self.assertNotIn('class="eq"', s)

    def test_now_playing(self):
        s = self.svg(playing=True, ago=None)
        self.assertIn(" now playing ", s)
        self.assertIn('class="eq"', s)
        self.assertIn('aria-label="Now playing on Spotify', s)

    def test_art_embedded(self):
        s = self.svg(art="data:image/jpeg;base64,AAAA")
        self.assertIn('href="data:image/jpeg;base64,AAAA"', s)
        self.assertNotIn("♪", s)

    def test_escaping_and_empty_album(self):
        s = self.svg(track="Rock & <Roll>", album="")
        self.assertIn("Rock &amp; &lt;Roll&gt;", s)
        self.assertNotIn("# </", s)
        self.assertNotIn(">#  <", s)

    def test_long_title_clipped(self):
        s = self.svg(track="x" * 200)
        # visible line is cut; the aria-label keeps the full title on purpose
        self.assertIn(">" + "x" * 29 + "…</text>", s)

    def test_top_artists_column(self):
        s = self.svg()
        self.assertIn("# top this week", s)
        self.assertIn("she &amp; him", s)
        self.assertIn(">42</text>", s)
        self.assertIn("men i trust", s)
        self.assertIn("Top this week: She &amp; Him, Clairo, Men I Trust", s)  # aria-label

    def test_top_artists_empty(self):
        s = self.svg(top=[])
        self.assertIn("nothing yet", s)
        self.assertNotIn("Top this week:", s)

    def test_long_artist_in_top_clipped(self):
        s = self.svg(top=[("y" * 40, 5)])
        self.assertIn(">" + "y" * 17 + "…</text>", s)


class Live(unittest.TestCase):
    M = {"track": "Better Together", "artist": "Jack Johnson", "album": "In Between Dreams",
         "playing": False, "ago": "11h ago", "scrobbles": 111507, "art": None, "top": []}

    def test_music_svg_returns_markup_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            old, render.ASSETS = render.ASSETS, Path(d)
            try:
                out = render.music_svg(self.M)
            finally:
                render.ASSETS = old
            self.assertTrue(out.startswith("<svg"))
            self.assertIn("Better Together", out)
            self.assertEqual(list(Path(d).iterdir()), [])

    def live(self, fetch):
        old, render.fetch_music = render.fetch_music, fetch
        try:
            return render.live_music("key")
        finally:
            render.fetch_music = old

    def test_live_ok_caches_a_minute(self):
        body, ttl = self.live(lambda key: dict(self.M))
        self.assertIn("Better Together", body)
        self.assertEqual(ttl, 60)

    def test_live_failure_serves_offline_card_briefly(self):
        def boom(key):
            raise OSError("last.fm down")
        body, ttl = self.live(boom)
        self.assertIn("taking a nap", body)
        self.assertEqual(ttl, 10)

    def test_live_without_key_or_scrobbles(self):
        self.assertIn("taking a nap", render.live_music(None)[0])
        self.assertIn("taking a nap", self.live(lambda key: None)[0])

    def test_offline_card(self):
        out = render.music_offline_svg()
        self.assertTrue(out.startswith("<svg"))
        self.assertIn("last.fm is taking a nap", out)
        self.assertIn('width="840" height="188"', out)


class Top(unittest.TestCase):
    def test_parse_top(self):
        data = {"topartists": {"artist": [{"name": "She & Him", "playcount": "42"},
                                          {"name": "Clairo", "playcount": "31"}]}}
        self.assertEqual(render.parse_top(data), [("She & Him", 42), ("Clairo", 31)])

    def test_parse_top_single_dict_and_empty(self):
        one = {"topartists": {"artist": {"name": "Clairo", "playcount": "3"}}}
        self.assertEqual(render.parse_top(one), [("Clairo", 3)])
        self.assertEqual(render.parse_top({"topartists": {"artist": []}}), [])

    def test_parse_top_caps_at_three(self):
        data = {"topartists": {"artist": [{"name": str(i), "playcount": "1"} for i in range(5)]}}
        self.assertEqual(len(render.parse_top(data)), 3)


class Art(unittest.TestCase):
    def test_unreachable_art_is_none(self):
        self.assertIsNone(render.fetch_art("http://127.0.0.1:9/cover.jpg"))  # port 9: refused

    def test_no_url(self):
        self.assertIsNone(render.fetch_art(None))


if __name__ == "__main__":
    unittest.main()
