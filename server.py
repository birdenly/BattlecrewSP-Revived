"""
Local Parse Mock Server for Battlecrew Space Pirates
Port: 1337
URL: http://localhost:1337/parse
"""

import json
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 1337

class ParseMockHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        response_bytes = json.dumps(data).encode("utf-8")
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        print(f"[GET] {path} query={query}")

        if path.endswith("/config"):
            # GET /parse/config
            resp = {
                "params": {
                    "EnableBackEnd": True,
                    "LeaderboardUseBackEnd": True,
                    "Maintenance": False,
                    "ServerStatus": "Online",
                    "WALProperties": {
                        "TDMAvailable": True,
                        "GRAvailable": True,
                        "EnhancedMatchMaking": True,
                        "DailyFreeGames": 999,
                        "PPRatio": 1.0,
                        "EnableMatchMaking": True,
                        "JoinUsersTortuga": True,
                        "ServerStatus": "Online",
                        "Maintenance": False
                    },
                    "PlaylistProperties": {
                        "GRShuffle": True,
                        "TDMShuffle": True,
                        "SOLOShuffle": True
                    }
                }
            }
            self._send_json(200, resp)
            return

        elif "/users/me" in path:
            self._send_json(200, self._get_mock_user())
            return

        elif "/users" in path or "/login" in path:
            self._send_json(200, self._get_mock_user())
            return

        elif "/classes/FreeGamesTable" in path:
            resp = {
                "results": [
                    {
                        "objectId": "free_play_dm",
                        "gameMode": "DeathMatch",
                        "active": True,
                        "free": True,
                        "DailyFreeGame": 999,
                        "StackedFreeGame": 999
                    },
                    {
                        "objectId": "free_play_gr",
                        "gameMode": "GoldRush",
                        "active": True,
                        "free": True,
                        "DailyFreeGame": 999,
                        "StackedFreeGame": 999
                    }
                ]
            }
            self._send_json(200, resp)
            return

        elif "/classes/UserRanking" in path:
            resp = {
                "results": [
                    {
                        "objectId": "rank_01",
                        "userId": "pirate_local_01",
                        "username": "SpacePirate",
                        "score": 1000,
                        "rank": 1,
                        "tier": 1
                    }
                ]
            }
            self._send_json(200, resp)
            return

        elif "/classes/" in path:
            self._send_json(200, {"results": []})
            return

        # Default fallback for any other GET
        self._send_json(200, {"result": {}, "results": []})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        body_json = {}
        if body:
            try:
                body_json = json.loads(body.decode("utf-8"))
            except Exception:
                body_json = {"raw": body.decode("ascii", errors="ignore")}
        
        print(f"[POST] {path} body={body_json}")

        if path.endswith("/batch"):
            requests = body_json.get("requests", [])
            batch_results = []
            for req in requests:
                batch_results.append({
                    "success": {
                        "objectId": "batch_item_" + datetime.utcnow().strftime("%f"),
                        "createdAt": datetime.utcnow().isoformat() + "Z"
                    }
                })
            self._send_json(200, batch_results)
            return

        elif "/login" in path:
            self._send_json(200, self._get_mock_user())
            return

        elif "/users" in path:
            user = self._get_mock_user()
            self._send_json(201, user)
            return

        elif "/functions/" in path:
            func_name = path.split("/functions/")[-1]
            if func_name == "getCustomLeaderboard":
                self._send_json(200, {"result": {"leaderboard": []}})
            elif func_name == "getGameModeRanking":
                self._send_json(200, {"result": {"rankings": []}})
            elif func_name == "getScheduledRanking":
                self._send_json(200, {"result": {"scheduled": []}})
            else:
                self._send_json(200, {"result": {}})
            return

        elif "/classes/" in path:
            resp = {
                "objectId": "obj_" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
                "createdAt": datetime.utcnow().isoformat() + "Z"
            }
            self._send_json(201, resp)
            return

        # Fallback
        self._send_json(200, {"result": {}, "success": True})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        print(f"[PUT] {path} body={body.decode('utf-8', errors='ignore')}")

        resp = {
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        }
        self._send_json(200, resp)

    def do_DELETE(self):
        print(f"[DELETE] {self.path}")
        self._send_json(200, {})

    def _get_mock_user(self):
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "objectId": "pirate_local_01",
            "username": "SpacePirate",
            "nickname": "SpacePirate",
            "sessionToken": "r:bsp_local_session_token_9999",
            "createdAt": "2018-01-01T00:00:00.000Z",
            "updatedAt": now,
            "playingStatus": 0,
            "currentRank": 100,
            "level": 100,
            "Kills": 999,
            "KillDeath_Ratio": 5.0,
            "gold": 999999,
            "bounty": 999999
        }

    def log_message(self, format, *args):
        # Clean logging
        pass

def run():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, ParseMockHandler)
    print("=" * 60)
    print(f" Battlecrew Space Pirates - Parse Mock Server Running")
    print(f" Listening on http://localhost:{PORT}/parse")
    print(" App ID: awa | Key: latore")
    print(" Press Ctrl+C to stop.")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    run()

