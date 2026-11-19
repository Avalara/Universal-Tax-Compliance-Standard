#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Minimal web UI that runs the flower-shop happy path and lists HTTP steps."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from simple_happy_path_client import (
  _start_local_platform_profile_server,
  run_happy_path,
)

logger = logging.getLogger(__name__)

_DEMO_PORT = 8765


class RunRequest(BaseModel):
  """POST /api/run body."""

  server_url: str = Field(
    default="http://localhost:8182",
    description="UCP merchant base URL",
  )
  tax_extension_url: str = Field(
    default="http://127.0.0.1:8080",
    description="Checkout tax extension base URL (empty string to skip)",
  )


@asynccontextmanager
async def _lifespan(app: FastAPI):
  profile_httpd, platform_profile_uri = _start_local_platform_profile_server(
    Path(__file__).resolve().parent
  )
  app.state.profile_httpd = profile_httpd
  app.state.platform_profile_uri = platform_profile_uri
  logger.info("Platform profile for UCP-Agent: %s", platform_profile_uri)
  yield
  profile_httpd.shutdown()


app = FastAPI(title="UCP Happy Path Demo", lifespan=_lifespan)


_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>UCP Happy Path Demo</title>
  <style>
    :root { font-family: system-ui, sans-serif; line-height: 1.45; }
    body { max-width: 52rem; margin: 1.5rem auto; padding: 0 1rem; }
    h1 { font-size: 1.25rem; }
    label { display: block; margin-top: 0.75rem; font-size: 0.9rem; }
    input[type="text"] {
      width: 100%; max-width: 28rem; padding: 0.35rem 0.5rem;
    }
    button {
      margin-top: 1rem; padding: 0.45rem 1rem; cursor: pointer;
    }
    #status { margin-top: 1rem; color: #444; }
    .step {
      border: 1px solid #ccc; border-radius: 6px; margin-top: 1rem;
      padding: 0.75rem 1rem; background: #fafafa;
    }
    .step h2 { font-size: 1rem; margin: 0 0 0.5rem 0; }
    .meta { font-size: 0.85rem; color: #333; margin-bottom: 0.5rem; }
    pre {
      font-size: 0.75rem; overflow: auto; max-height: 14rem;
      background: #fff; border: 1px solid #e0e0e0; padding: 0.5rem;
    }
    .err { color: #a30; }
    .ok { color: #060; }
  </style>
</head>
<body>
  <h1>UCP happy path (flower shop)</h1>
  <p>Runs the same flow as <code>simple_happy_path_client.py</code> on the
    server and shows each HTTP interaction below.</p>
  <form id="f" action="#" method="post">
    <label>Merchant server URL
      <input type="text" name="server_url" id="server_url"
        value="http://localhost:8182" autocomplete="off"/>
    </label>
    <label>Tax extension URL (optional; use empty to skip)
      <input type="text" name="tax_extension_url" id="tax_extension_url"
        value="http://127.0.0.1:8080" autocomplete="off"/>
    </label>
    <button type="submit" id="go">Run happy path</button>
  </form>
  <p id="status"></p>
  <div id="out"></div>
  <script>
  const statusEl = document.getElementById("status");
  const outEl = document.getElementById("out");
  document.getElementById("f").addEventListener("submit", async (e) => {
    e.preventDefault();
    outEl.innerHTML = "";
    statusEl.textContent = "Running…";
    statusEl.className = "";
    const server_url = document.getElementById("server_url").value.trim();
    const tax_extension_url =
      document.getElementById("tax_extension_url").value.trim();
    try {
      const r = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ server_url, tax_extension_url }),
      });
      const data = await r.json();
      if (!r.ok) {
        statusEl.textContent =
          "HTTP " + r.status + ": " + (data.detail || r.statusText);
        statusEl.className = "err";
        return;
      }
      if (data.ok) {
        statusEl.textContent = "Completed. Order " + (data.order_id || "") +
          (data.order_permalink ? " — " + data.order_permalink : "");
        statusEl.className = "ok";
      } else {
        statusEl.textContent = "Stopped: " + (data.error || "unknown error");
        statusEl.className = "err";
      }
      const steps = data.steps || [];
      steps.forEach((s, i) => {
        const d = document.createElement("div");
        d.className = "step";
        const title = document.createElement("h2");
        title.textContent = s.step || ("Step " + (i + 1));
        d.appendChild(title);
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = s.method + " " + s.url + " → HTTP " + s.status_code;
        d.appendChild(meta);
        if (s.request_headers && Object.keys(s.request_headers).length) {
          const h = document.createElement("p");
          h.textContent = "Request headers";
          d.appendChild(h);
          const pre = document.createElement("pre");
          pre.textContent = JSON.stringify(s.request_headers, null, 2);
          d.appendChild(pre);
        }
        if (s.request_body != null) {
          const p = document.createElement("p");
          p.textContent = "Request body";
          d.appendChild(p);
          const pre = document.createElement("pre");
          pre.textContent = JSON.stringify(s.request_body, null, 2);
          d.appendChild(pre);
        }
        const pr = document.createElement("p");
        pr.textContent = "Response body";
        d.appendChild(pr);
        const preR = document.createElement("pre");
        preR.textContent = typeof s.response_body === "string"
          ? s.response_body
          : JSON.stringify(s.response_body, null, 2);
        d.appendChild(preR);
        outEl.appendChild(d);
      });
    } catch (err) {
      statusEl.textContent = String(err);
      statusEl.className = "err";
    }
  });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
  """Serve the demo page."""
  return _INDEX_HTML


@app.post("/api/run")
def api_run(req: RunRequest) -> dict[str, object]:
  """Execute the happy path and return structured steps."""
  interactions: list[dict[str, object]] = []
  base = req.server_url.rstrip("/")
  try:
    with httpx.Client(base_url=base, timeout=60.0) as client:
      result = run_happy_path(
        logger=logger,
        client=client,
        server_url=base,
        platform_profile_uri=app.state.platform_profile_uri,
        tax_extension_url=req.tax_extension_url,
        export_requests_to=None,
        interactions_out=interactions,
      )
  except httpx.HTTPError as exc:
    logger.warning("Happy path HTTP error: %s", exc)
    err = str(exc)
  except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.exception("Happy path failed")
    err = str(exc)
  else:
    return {
      "ok": result.ok,
      "error": result.error_message,
      "steps": interactions,
      "order_id": result.order_id,
      "order_permalink": result.order_permalink,
    }
  return {
    "ok": False,
    "error": err,
    "steps": interactions,
    "order_id": None,
    "order_permalink": None,
  }


def main() -> None:
  """Run the demo app with uvicorn."""
  logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
  )
  uvicorn.run(
    "happy_path_demo_app:app",
    host="127.0.0.1",
    port=_DEMO_PORT,
    reload=False,
  )


if __name__ == "__main__":
  main()
