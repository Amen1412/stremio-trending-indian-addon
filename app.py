from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "29dfffa9ae088178fa088680b67ce583"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

TARGET_LANGUAGES = ["hi", "te", "ta", "ml", "kn"]  # Indian languages
all_trending_cache = []

def fetch_trending_indian_content():
    global all_trending_cache
    print("[CACHE] Fetching trending Indian content...")

    today = datetime.now().strftime("%Y-%m-%d")
    collected = []

    def fetch_from(endpoint, media_type):
        for page in range(1, 10):
            params = {
                "api_key": TMDB_API_KEY,
                "sort_by": "popularity.desc",
                "region": "IN",
                "watch_region": "IN",
                "page": page,
                "release_date.lte": today
            }
            try:
                response = requests.get(f"{TMDB_BASE_URL}/discover/{endpoint}", params=params)
                results = response.json().get("results", [])
                if not results:
                    break
                for item in results:
                    lang = item.get("original_language")
                    if lang in TARGET_LANGUAGES:
                        item["media_type"] = media_type
                        collected.append(item)
            except Exception as e:
                print(f"[ERROR] {media_type} page {page} failed: {e}")
                break

    fetch_from("movie", "movie")
    fetch_from("tv", "series")

    seen_ids = set()
    unique = []
    for item in collected:
        item_id = item.get("id")
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            unique.append(item)

    all_trending_cache = unique[:100]  # limit to top 100
    print(f"[CACHE] Fetched {len(all_trending_cache)} trending Indian titles ✅")

def to_stremio_meta(item):
    try:
        name = item.get("title") or item.get("name")
        poster = item.get("poster_path")
        backdrop = item.get("backdrop_path")
        return {
            "id": f"{item['media_type']}_{item['id']}",
            "type": "movie" if item["media_type"] == "movie" else "series",
            "name": name,
            "poster": f"https://image.tmdb.org/t/p/w500{poster}" if poster else None,
            "description": item.get("overview", ""),
            "releaseInfo": item.get("release_date") or item.get("first_air_date", ""),
            "background": f"https://image.tmdb.org/t/p/w780{backdrop}" if backdrop else None
        }
    except Exception as e:
        print(f"[ERROR] to_stremio_meta failed: {e}")
        return None

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "id": "org.trending.indian.catalog",
        "version": "1.0.0",
        "name": "Trending Indian",
        "description": "Top trending Indian Movies and Shows",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [{
            "type": "movie",
            "id": "trending-indian",
            "name": "Trending Indian"
        }, {
            "type": "series",
            "id": "trending-indian",
            "name": "Trending Indian"
        }],
        "idPrefixes": []
    })

@app.route("/catalog/<type>/<catalog_id>.json")
def catalog(type, catalog_id):
    if catalog_id != "trending-indian":
        return jsonify({"metas": []})

    print(f"[INFO] Catalog requested: {type}")
    try:
        metas = [to_stremio_meta(m) for m in all_trending_cache if m["media_type"] == type]
        return jsonify({"metas": [m for m in metas if m]})
    except Exception as e:
        print(f"[ERROR] Catalog error: {e}")
        return jsonify({"metas": []})

@app.route("/refresh")
def refresh():
    def do_refresh():
        try:
            fetch_trending_indian_content()
            print("[REFRESH] Background refresh complete ✅")
        except Exception as e:
            import traceback
            print(f"[REFRESH ERROR] {traceback.format_exc()}")

    threading.Thread(target=do_refresh).start()
    return jsonify({"status": "refresh started in background"})

# Initial fetch
fetch_trending_indian_content()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
