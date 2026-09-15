import urllib.parse, requests
from configs.settings import settings
base = settings.OPENDOTA_BASE_URL
key = settings.OPENDOTA_API_KEY

def try_sql(sql, label):
    url = f"{base}/explorer?sql={urllib.parse.quote(sql)}"
    if key:
        url += f"&api_key={key}"
    print(f"\n--- {label}")
    print(sql[:300])
    r = requests.get(url, timeout=30)
    print("status", r.status_code)
    print(r.text[:4000])
    return r

try_sql("SELECT match_id FROM public_matches LIMIT 1", "simple public_matches")
try_sql("SELECT pm.match_id, ppm.hero_id FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id LIMIT 1", "simple join")
try_sql("SELECT pm.match_id, pm.start_time, pm.duration, pm.radiant_win, pm.avg_rank_tier, ppm.hero_id, ppm.player_slot FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id WHERE pm.lobby_type = 7 AND pm.game_mode = 22 AND pm.duration >= 1200 AND pm.avg_rank_tier IS NOT NULL AND pm.avg_rank_tier >= 40 AND pm.avg_rank_tier < 50 ORDER BY pm.match_id DESC LIMIT 10", "full draft query")
try_sql("SELECT pm.match_id, pm.start_time, pm.duration, pm.radiant_win, pm.avg_rank_tier, ppm.hero_id, ppm.player_slot FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id WHERE pm.lobby_type = 7 AND pm.game_mode = 22 AND pm.duration >= 1200 AND pm.avg_rank_tier IS NOT NULL AND pm.avg_rank_tier >= 40 AND pm.avg_rank_tier < 50 ORDER BY pm.match_id DESC LIMIT 100", "limit100")
# try without ORDER BY?
try_sql("SELECT pm.match_id, ppm.hero_id FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id WHERE pm.match_id < 8000000000 ORDER BY pm.match_id DESC LIMIT 10", "join with before filter")
