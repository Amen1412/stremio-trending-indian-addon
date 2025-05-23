from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "29dfffa9ae088178fa088680b67ce583"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

TARGET_LANGUAGES = ["hi", "te", "ta", "ml", "kn"]
all_movies_cache = []

def fetch_trending_movies():
    global all_movies_cache
    print("[CACHE] Fetching trending Indian movies...")

    today = datetime.now().strftime("%Y-%m-%d")
    collected = []

    for page in range(1, 25):  # Go deeper to get more results
        print(f"[INFO] Checking page {page}")
        params = {
            "api_key": TMDB_API_KEY,
            "sort_by": "popularity.desc",
            "region": "IN",
            "watch_region": "IN",
            "page": page,
            "release_date.lte": today
        }

        try:
            response = requests.get(f"{TMDB_BASE_URL}/discover/movie", params=params)
            results = response.json().get("results", [])
            if not results:
                break
            for movie in results:
                lang = movie.get("original_language")
                if lang not in TARGET_LANGUAGES:
                    continue

                movie_id = movie.get("id")
                if not movie_id or not movie.get("title") or not movie.get("poster_path"):
                    continue

                # Check OTT availability in India
                prov_url = f"{TMDB_BASE_URL}/movie/{movie_id}/watch/providers"
                prov_response = requests.get(prov_url, params={"api_key": TMDB_API_KEY})
                prov_data = prov_response.json()
                if "results" in prov_data and "IN" in prov_data["results"]:
                    if "flatrate" in prov_data["results"]["IN"]:
                        movie["media_type"] = "movie"
                        collected.append(movie)

                if len(collected) >= 100:
                    break
            if len(collected) >= 100:
                break

        except Exception as e:
            print(f"[ERROR] Page {page} failed: {e}")
            break

    # Deduplicate and clean
    seen_ids = set()
    unique = []
    for movie in collected:
        movie_id = movie.get("id")
        if movie_id and movie_id not in seen_ids:
            seen_ids.add(movie_id)
            unique.append(movie)

    all_movies_cache = unique
    print(f"[CACHE] Fetched {len(all_movies_cache)} trending Indian movies ✅")

def to_stremio_meta(movie):
    try:
        return {
            "id": f"movie_{movie['id']}",
            "type": "movie",
            "name": movie.get("title"),
            "poster": f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None,
            "description": movie.get("overview", ""),
            "releaseInfo": movie.get("release_date", ""),
            "background": f"https://image.tmdb.org/t/p/w780{movie['backdrop_path']}" if movie.get("backdrop_path") else None
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
        "description": "Top trending Indian Movies",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{
            "type": "movie",
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
        metas = [to_stremio_meta(m) for m in all_movies_cache]
        return jsonify({"metas": [m for m in metas if m]})
    except Exception as e:
        print(f"[ERROR] Catalog error: {e}")
        return jsonify({"metas": []})

@app.route("/refresh")
def refresh():
    def do_refresh():
        try:
            fetch_trending_movies()
            print("[REFRESH] Background refresh complete ✅")
        except Exception as e:
            import traceback
            print(f"[REFRESH ERROR] {traceback.format_exc()}")

    threading.Thread(target=do_refresh).start()
    return jsonify({"status": "refresh started in background"})

# Initial fetch
fetch_trending_movies()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
