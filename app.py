from flask import Flask, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

TRAKT_CLIENT_ID = "218a2d878742b678260a43508b4ab7eb7747d0841ef9934b86e90327350fdc6a"

# Global cache
trending_cache = []

def fetch_trending_from_trakt():
    global trending_cache
    print("[CACHE] Fetching trending Indian content...")

    trending_cache = []

    headers = {
        "Content-Type": "application/json",
        "trakt-api-key": TRAKT_CLIENT_ID,
        "trakt-api-version": "2"
    }

    for content_type in ["movies", "shows"]:
        try:
            response = requests.get(
                f"https://api.trakt.tv/trending/{content_type}",
                headers=headers,
                params={"limit": 50}  # adjust if needed
            )

            items = response.json()

            for item in items:
                data = item.get(content_type[:-1])  # "movie" or "show"
                if not data:
                    continue

                title = data.get("title")
                year = data.get("year")
                ids = data.get("ids", {})
                imdb_id = ids.get("imdb")

                if imdb_id and imdb_id.startswith("tt") and title:
                    trending_cache.append({
                        "id": imdb_id,
                        "type": "movie" if content_type == "movies" else "series",
                        "name": title,
                        "poster": None,
                        "description": f"{title} ({year})",
                        "releaseInfo": str(year),
                        "background": None
                    })

        except Exception as e:
            print(f"[ERROR] Failed to fetch trending {content_type}: {e}")

    print(f"[CACHE] Fetched {len(trending_cache)} trending Indian titles ✅")


@app.route("/manifest.json")
def manifest():
    return jsonify({
        "id": "org.trending.indian",
        "version": "1.0.0",
        "name": "Trending Indian",
        "description": "Trending Indian Movies and Shows",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {
                "type": "movie",
                "id": "trending_indian",
                "name": "Trending Indian"
            },
            {
                "type": "series",
                "id": "trending_indian",
                "name": "Trending Indian"
            }
        ],
        "idPrefixes": ["tt"]
    })


@app.route("/catalog/<type>/trending_indian.json")
def catalog(type):
    print(f"[INFO] Catalog requested for {type}")
    filtered = [item for item in trending_cache if item["type"] == type]
    return jsonify({"metas": filtered})


@app.route("/refresh")
def refresh():
    try:
        fetch_trending_from_trakt()
        return jsonify({"status": "refreshed", "count": len(trending_cache)})
    except Exception as e:
        return jsonify({"error": str(e)})

# Fetch on startup
fetch_trending_from_trakt()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
