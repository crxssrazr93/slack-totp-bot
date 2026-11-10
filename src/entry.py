"""Cloudflare Worker entry point.

fetch:     POST /slack/commands  handles the /totp slash command.
scheduled: every minute, rewrites the live board message twice (on each 30 second boundary).
"""

import asyncio
import json
import time
from urllib.parse import parse_qs, urlparse

from workers import Response, WorkerEntrypoint, fetch

import slack
from accounts import parse_rows
from sheets import read_sheet

BOARD_KEY = "board_message_ts"
REFRESH_SECONDS = 30


class Default(WorkerEntrypoint):
    async def _accounts(self):
        # The only place that knows where secrets live. To use another store,
        # return rows in the same shape (header row first). See docs/alternatives.md.
        values = await read_sheet(
            self.env.GOOGLE_SERVICE_ACCOUNT_JSON,
            self.env.SHEET_ID,
            getattr(self.env, "SHEET_RANGE", None) or "TOTP!A:Z",
        )
        return parse_rows(values)

    async def fetch(self, request):
        if request.method != "POST" or urlparse(str(request.url)).path != "/slack/commands":
            return Response("Not found", status=404)

        body = await request.text()
        if not slack.verify_signature(
            self.env.SLACK_SIGNING_SECRET,
            request.headers.get("x-slack-request-timestamp"),
            body,
            request.headers.get("x-slack-signature"),
            time.time(),
        ):
            return Response("Invalid signature", status=401)

        form = {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}
        if form.get("channel_id") != self.env.SLACK_CHANNEL_ID:
            return Response.json({
                "response_type": "ephemeral",
                "text": "This command only works in the shared 2FA channel.",
            })

        try:
            accounts, problems = await self._accounts()
        except Exception as error:  # noqa: BLE001
            print(f"sheet read failed: {error}")
            return Response.json({"response_type": "ephemeral", "text": "Could not read the codes sheet. Check the Worker logs."})
        return Response.json(slack.command_response(accounts, problems, form.get("text", ""), time.time()))

    async def scheduled(self, controller, env, ctx):
        # Cron Triggers fire at most once a minute, so refresh now and again on
        # the next 30 second boundary (1s late to be safely inside the new window).
        await self._update_board()
        now = time.time()
        await asyncio.sleep((int(now // REFRESH_SECONDS) + 1) * REFRESH_SECONDS - now + 1)
        await self._update_board()

    async def _update_board(self):
        accounts, problems = await self._accounts()
        message = slack.board_message(accounts, problems, time.time())
        message["channel"] = self.env.SLACK_CHANNEL_ID

        ts = await self.env.BOARD.get(BOARD_KEY)
        if ts:
            result = await self._slack("chat.update", {**message, "ts": ts})
            if result.get("ok"):
                return
            print(f"chat.update failed ({result.get('error')}), posting a new board")

        result = await self._slack("chat.postMessage", message)
        if not result.get("ok"):
            raise RuntimeError(f"chat.postMessage failed: {result.get('error')}")
        await self.env.BOARD.put(BOARD_KEY, result["ts"])
        pin = await self._slack("pins.add", {"channel": message["channel"], "timestamp": result["ts"]})
        if not pin.get("ok"):
            print(f"pins.add failed: {pin.get('error')}")

    async def _slack(self, method: str, payload: dict) -> dict:
        response = await fetch(
            f"https://slack.com/api/{method}",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.env.SLACK_BOT_TOKEN}",
                "Content-Type": "application/json; charset=utf-8",
            },
            body=json.dumps(payload),
        )
        return json.loads(await response.text())
