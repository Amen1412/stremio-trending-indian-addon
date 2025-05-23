from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "29dfffa9ae088178fa088680b67ce583"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

INDIAN_LANGUAGES = {"hi", "ml", "ta", "te", "kn"}
all_movies_cache = []

def fetch_and_cache_movies():
    global all_movies_cache
    print("[CACHE] Fetching trending Indian movies...")

    today = datetime.now().strftime("%Y-%m-%d")
    final_movies = []
    seen_ids = set()

    page = 1
    while len(final_movies) < 100:
        print(f"[INFO] Checking page {page}")
        params = {
            "api_key": TMDB_API_KEY,
            "sort_by": "popularity.desc",
            "release_date.lte": today,
            "watch_region": "IN",
            "page": page
        }

        try:
            response = requests.get(f"{TMDB_BASE_URL}/discover/movie", params=params)
            results = response.json().get("results", [])
            if not results:
                break

            for movie in results:
                if len(final_movies) >= 100:
                    break

                movie_id = movie.get("id")
                lang = movie.get("original_language")
                if not movie_id or lang not in INDIAN_LANGUAGES:
                    continue

                # Check OTT availability
                providers_url = f"{TMDB_BASE_URL}/movie/{movie_id}/watch/providers"
                prov_response = requests.get(providers_url, params={"api_key": TMDB_API_KEY})
                prov_data = prov_response.json()

                if "results" in prov_data and "IN" in prov_data["results"]:
                    if "flatrate" in prov_data["results"]["IN"]:
                        # Get IMDb ID
                        ext_url = f"{TMDB_BASE_URL}/movie/{movie_id}/external_ids"
                        ext_response = requests.get(ext_url, params={"api_key": TMDB_API_KEY})
                        ext_data = ext_response.json()
                        imdb_id = ext_data.get("imdb_id")

                        if imdb_id and imdb_id.startswith("tt") and imdb_id not in seen_ids:
                            seen_ids.add(imdb_id)
                            movie["imdb_id"] = imdb_id
                            final_movies.append(movie)

        except Exception as e:
            print(f"[ERROR] Page {page} failed: {e}")
            break

        page += 1

    all_movies_cache = final_movies
    print(f"[CACHE] Fetched {len(all_movies_cache)} trending Indian movies ✅")


def to_stremio_meta(movie):
    try:
        imdb_id = movie.get("imdb_id")
        title = movie.get("title")
        if not imdb_id or not title:
            return None

        return {
            "id": imdb_id,
            "type": "movie",
            "name": title,
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
        "description": "Trending Indian Movies on OTT (Hindi, Malayalam, Tamil, Telugu, Kannada)",
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
    print("[INFO] Catalog requested")
    try:
        metas = [meta for meta in (to_stremio_meta(m) for m in all_movies_cache) if meta]
        print(f"[INFO] Returning {len(metas)} total movies ✅")
        return jsonify({"metas": metas})
    except Exception as e:
        print(f"[ERROR] Catalog error: {e}")
        return jsonify({"metas": []})


@app.route("/refresh")
def refresh():
    def do_refresh():
        try:
            fetch_and_cache_movies()
            print("[REFRESH] Background refresh complete ✅")
        except Exception as e:
            import traceback
            print(f"[REFRESH ERROR] {traceback.format_exc()}")

    threading.Thread(target=do_refresh).start()
    return jsonify({"status": "refresh started in background"})


# Fetch on startup
fetch_and_cache_movies()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
