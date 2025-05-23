from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "29dfffa9ae088178fa088680b67ce583"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

all_trending_cache = []


def fetch_trending_content():
    global all_trending_cache
    print("[CACHE] Fetching trending Indian content...")

    final_items = []
    endpoints = ["movie", "tv"]

    for media_type in endpoints:
        try:
            url = f"{TMDB_BASE_URL}/trending/{media_type}/day"
            params = {"api_key": TMDB_API_KEY}
            res = requests.get(url, params=params)
            results = res.json().get("results", [])

            for item in results:
                if not item.get("id") or not item.get("title") and not item.get("name"):
                    continue

                # Filter for Indian origin content if available
                if "origin_country" in item and "IN" not in item["origin_country"]:
                    continue

                # Check if it has watch providers (optional)
                providers_url = f"{TMDB_BASE_URL}/{media_type}/{item['id']}/watch/providers"
                prov_res = requests.get(providers_url, params={"api_key": TMDB_API_KEY})
                prov_data = prov_res.json()

                if "results" in prov_data and "IN" in prov_data["results"]:
                    if "flatrate" in prov_data["results"]["IN"]:
                        # Get IMDb ID
                        ext_url = f"{TMDB_BASE_URL}/{media_type}/{item['id']}/external_ids"
                        ext_res = requests.get(ext_url, params={"api_key": TMDB_API_KEY})
                        ext_data = ext_res.json()
                        imdb_id = ext_data.get("imdb_id")

                        if imdb_id and imdb_id.startswith("tt"):
                            item["imdb_id"] = imdb_id
                            item["media_type"] = media_type
                            final_items.append(item)

        except Exception as e:
            print(f"[ERROR] Fetching trending {media_type}: {e}")

    # Remove duplicates by IMDb ID
    seen = set()
    unique_items = []
    for i in final_items:
        imdb = i.get("imdb_id")
        if imdb and imdb not in seen:
            seen.add(imdb)
            unique_items.append(i)

    all_trending_cache = unique_items[:100]
    print(f"[CACHE] Fetched {len(all_trending_cache)} trending Indian items ✅")


def to_stremio_meta(item):
    try:
        imdb_id = item.get("imdb_id")
        title = item.get("title") or item.get("name")
        media_type = item.get("media_type", "movie")
        if not imdb_id or not title:
            return None

        return {
            "id": imdb_id,
            "type": media_type,
            "name": title,
            "poster": f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else None,
            "description": item.get("overview", ""),
            "releaseInfo": item.get("release_date") or item.get("first_air_date", ""),
            "background": f"https://image.tmdb.org/t/p/w780{item['backdrop_path']}" if item.get("backdrop_path") else None
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
        "description": "Trending Indian Movies and Shows",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{
            "type": "movie",
            "id": "trending-indian",
            "name": "Trending Indian"
        }],
        "idPrefixes": ["tt"]
    })


@app.route("/catalog/movie/trending-indian.json")
def catalog():
    print("[INFO] Trending catalog requested")
    try:
        metas = [meta for meta in (to_stremio_meta(i) for i in all_trending_cache) if meta]
        print(f"[INFO] Returning {len(metas)} trending items ✅")
        return jsonify({"metas": metas})
    except Exception as e:
        print(f"[ERROR] Catalog error: {e}")
        return jsonify({"metas": []})


@app.route("/refresh")
def refresh():
    def do_refresh():
        try:
            fetch_trending_content()
            print("[REFRESH] Background refresh complete ✅")
        except Exception as e:
            import traceback
            print(f"[REFRESH ERROR] {traceback.format_exc()}")

    threading.Thread(target=do_refresh).start()
    return jsonify({"status": "refresh started in background"})


# Fetch on startup
fetch_trending_content()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
