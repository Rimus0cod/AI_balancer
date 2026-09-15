import urllib.parse, requests, pathlib
from configs.settings import settings
base = settings.OPENDOTA_BASE_URL
key = settings.OPENDOTA_API_KEY
out = pathlib.Path("probe_out.txt")
out.write_text("", encoding="utf-8")

def try_sql(sql, label):
    url = f"{base}/explorer?sql={urllib.parse.quote(sql)}"
    if key:
        url += f"&api_key={key}"
    with out.open("a", encoding="utf-8") as f:
        f.write(f"\n--- {label}\n")
        f.write(sql[:600]+"\n")
        try:
            r = requests.get(url, timeout=30)
            f.write(f"status {r.status_code}\n")
            f.write(r.text[:5000]+"\n")
        except Exception as e:
            f.write(f"exc {e}\n")

try_sql("SELECT match_id FROM public_matches LIMIT 1", "simple")
try_sql("SELECT pm.match_id, ppm.hero_id FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id LIMIT 1", "join1")
try_sql("SELECT pm.match_id, pm.start_time, pm.duration, pm.radiant_win, pm.avg_rank_tier, ppm.hero_id, ppm.player_slot FROM public_matches pm JOIN public_player_matches ppm ON pm.match_id = ppm.match_id WHERE pm.lobby_type = 7 AND pm.game_mode = 22 AND pm.duration >= 1200 AND pm.avg_rank_tier IS NOT NULL AND pm.avg_rank_tier >= 40 AND pm.avg_rank_tier < 50 ORDER BY pm.match_id DESC LIMIT 10", "full10")
