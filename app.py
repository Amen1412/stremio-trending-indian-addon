from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "29dfffa9ae088178fa088680b67ce583"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
all_items_cache = []

def fetch_trending_content():
    global all_items_cache
    print("[CACHE] Fetching trending Indian content...")
    final_items = []

    for media_type in ["movie", "tv"]:
        try:
            url = f"{TMDB_BASE_URL}/trending/{media_type}/day"
            response = requests.get(url, params={"api_key": TMDB_API_KEY})
            results = response.json().get("results", [])
            for item in results:
                if item.get("original_language") not in ["hi", "ta", "te", "ml", "bn", "mr", "kn", "gu", "pa"]:  # Indian languages
                    continue
                item_id = item.get("id")
                title = item.get("title") or item.get("name")
                if not item_id or not title:
                    continue

                imdb_id = None
                if media_type == "movie":
                    ext_url = f"{TMDB_BASE_URL}/movie/{item_id}/external_ids"
                else:
                    ext_url = f"{TMDB_BASE_URL}/tv/{item_id}/external_ids"

                ext_response = requests.get(ext_url, params={"api_key": TMDB_API_KEY})
                ext_data = ext_response.json()
                imdb_id = ext_data.get("imdb_id")

                if imdb_id and imdb_id.startswith("tt"):
                    item["type"] = media_type
                    item["imdb_id"] = imdb_id
                    final_items.append(item)

        except Exception as e:
            print(f"[ERROR] Failed to fetch {media_type}: {e}")

    all_items_cache = final_items
    print(f"[CACHE] Fetched {len(all_items_cache)} trending Indian titles ✅")

def to_stremio_meta(item):
    try:
        imdb_id = item.get("imdb_id")
        title = item.get("title") or item.get("name")
        if not imdb_id or not title:
            return None

        return {
            "id": imdb_id,
            "type": "movie",  # Even TV shows are marked as 'movie' to work in Stremio
            "name": title,
            "poster": f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get("poster_path") else None,
            "description": item.get("overview", ""),
            "releaseInfo": item.get("release_date") or item.get("first_air_date", ""),
            "background": f"https://image.tmdb.org/t/p/w780{item.get('backdrop_path')}" if item.get("backdrop_path") else None
        }
    except Exception as e:
        print(f"[ERROR] to_stremio_meta failed: {e}")
        return None

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "id": "org.indian.trending",
        "version": "1.0.0",
        "name": "Trending Indian",
        "description": "Trending Indian Movies and Shows",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{
            "type": "movie",
            "id": "trending_indian",
            "name": "Trending Indian"
        }],
        "idPrefixes": ["tt"]
    })

@app.route("/catalog/movie/trending_indian.json")
def catalog():
    print("[INFO] Catalog requested")
    try:
        metas = [meta for meta in (to_stremio_meta(i) for i in all_items_cache) if meta]
        print(f"[INFO] Returning {len(metas)} total trending items ✅")
        return jsonify({"metas": metas})
    except Exception as e:
        print(f"[ERROR] Catalog error: {e}")
        return jsonify({"metas": []})

@app.route("/refresh")
def refresh():
    try:
        fetch_trending_content()
        return jsonify({"status": "refreshed", "count": len(all_items_cache)})
    except Exception as e:
        return jsonify({"error": str(e)})

# Initial fetch
fetch_trending_content()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
