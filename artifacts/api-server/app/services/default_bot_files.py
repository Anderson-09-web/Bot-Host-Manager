"""
Default bot files seeded to R2 on first startup.
Only uploaded if the file does NOT already exist in R2.
"""

# ── config_manager.py ─────────────────────────────────────────────────────────
# config_manager.py is the ONLY exception: it is always re-uploaded so that
# bug-fixes and improvements reach every deployment automatically.
# Users should not edit this file — it is a read-only utility module.
CONFIG_MANAGER_PY = '''\
"""
Persistent per-server configuration manager.
Stores all settings in the panel\'s PostgreSQL database via its internal API.
Configurations survive bot restarts and Render redeploys — no files, no R2 uploads.

Each cog should create its own namespaced instance so configs from different
cogs are stored separately and cleaned up independently when a cog is deleted.

Recommended usage (one line at the top of your cog file)
---------------------------------------------------------
    from config_manager import ConfigManager
    cfg = ConfigManager(__name__)   # __name__ = e.g. "cogs.welcome" → namespace "welcome"

    # Read a value (returns None if not set)
    channel_id = cfg.get(guild.id, "welcome_channel")

    # Save a value (persisted to the database immediately)
    cfg.set(guild.id, "welcome_channel", channel.id)
    cfg.set(guild.id, "welcome_message", "Welcome {mention} to {server}!")

    # Delete a single key
    cfg.delete(guild.id, "welcome_channel")

    # Get all settings stored by this cog for a server
    server_cfg = cfg.get_server(guild.id)   # returns a dict copy

    # Replace all this cog\'s settings for a server at once
    cfg.set_server(guild.id, {"welcome_channel": 123})

    # Remove all this cog\'s settings for a server
    cfg.clear_server(guild.id)

Legacy module-level API (still supported, uses "_global" namespace)
--------------------------------------------------------------------
    import config_manager as cfg
    cfg.get(guild.id, "key")    # works but shares one namespace with everything
"""

import json
import os
import threading
import time
import urllib.request
import urllib.error

# ── Panel API config (injected by the bot manager at startup) ─────────────────
_API_URL = os.getenv("PANEL_API_URL", "").rstrip("/")
_BOT_KEY = os.getenv("PANEL_BOT_KEY", "")

# ── Module-level cache (used by legacy functions) ─────────────────────────────
_lock          = threading.Lock()
_cache: dict   = {}      # {guild_id: {full_key: value}}  — raw DB keys with namespace
_loaded        = False   # True once the DB was successfully fetched (or retries exhausted)
_load_attempts = 0       # how many times _ensure_loaded has tried and failed
_MAX_ATTEMPTS  = 8       # give up after this many consecutive failures


# ── Internal ──────────────────────────────────────────────────────────────────

def _api_available() -> bool:
    return bool(_API_URL and _BOT_KEY)


def _request(method: str, path: str, body=None):
    """Make a synchronous HTTP request to the panel API.

    Returns the parsed JSON response, or None on any error.
    Errors are logged but never raised — the bot keeps running.
    """
    if not _api_available():
        return None
    url = f"{_API_URL}/api/bot-data{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {_BOT_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"[config_manager] API error {e.code} on {method} {path}: {e.reason}", flush=True)
        return None
    except Exception as e:
        print(f"[config_manager] API unreachable ({method} {path}): {e}", flush=True)
        return None


_WRITE_RETRIES = 3   # how many times to retry a failed PUT/DELETE before giving up
_WRITE_RETRY_DELAY = 1.0  # seconds between retries


def _request_write(method: str, path: str, body=None) -> bool:
    """Like _request() but for write operations (PUT / DELETE).

    Retries up to _WRITE_RETRIES times on failure and returns True if the
    API confirmed the write, False if all attempts failed.  The local cache
    is NOT touched here — callers must update it themselves before calling.
    """
    for attempt in range(1, _WRITE_RETRIES + 1):
        result = _request(method, path, body)
        if result is not None:
            return True
        if attempt < _WRITE_RETRIES:
            time.sleep(_WRITE_RETRY_DELAY)
    print(
        f"[config_manager] ⚠️  Write failed after {_WRITE_RETRIES} attempts"
        f" ({method} {path}) — change saved in memory only and will be"
        " lost on bot restart.",
        flush=True,
    )
    return False


def _ensure_loaded():
    """Lazy-load the full guild config from the database on first access.

    If the panel API is not yet ready (race condition at bot startup), this
    method does NOT mark the cache as loaded — the next call will retry.
    Only after _MAX_ATTEMPTS consecutive failures does it give up and run
    in-memory-only for the session, to avoid hammering a permanently-down API.
    """
    global _cache, _loaded, _load_attempts
    if _loaded:
        return
    result = _request("GET", "")
    if result is not None:
        _cache = result
        _loaded = True
        _load_attempts = 0
        print(f"[config_manager] Loaded config for {len(_cache)} server(s) from database.", flush=True)
    else:
        _load_attempts += 1
        if _load_attempts >= _MAX_ATTEMPTS:
            # API appears permanently unreachable — stop retrying.
            _loaded = True
            print(
                f"[config_manager] Warning: panel API unreachable after {_load_attempts} attempts"
                " — running in-memory only for this session.",
                flush=True,
            )
        else:
            print(
                f"[config_manager] Warning: panel API not ready yet"
                f" (attempt {_load_attempts}/{_MAX_ATTEMPTS}) — will retry on next access.",
                flush=True,
            )


# ── ConfigManager class (namespaced — recommended) ────────────────────────────

class ConfigManager:
    """
    Per-cog namespaced config manager.

    All keys are stored in the DB as ``{namespace}/{key}`` so configs from
    different cogs are isolated.  When the cog file is deleted via the panel,
    all entries for its namespace are automatically purged from the database.

    Parameters
    ----------
    module_name : str
        Pass ``__name__`` from your cog file.
        ``"cogs.welcome"`` → namespace ``"welcome"``
        ``"welcome"``      → namespace ``"welcome"``
    """

    def __init__(self, module_name: str):
        # Use only the last segment (e.g. "cogs.welcome" → "welcome")
        self._ns = module_name.split(".")[-1]

    def _full_key(self, key: str) -> str:
        return f"{self._ns}/{key}"

    def _strip_ns(self, full_key: str) -> str | None:
        prefix = f"{self._ns}/"
        if full_key.startswith(prefix):
            return full_key[len(prefix):]
        return None

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self, guild_id, key: str, default=None):
        """Get a single setting. Returns *default* when not set."""
        with _lock:
            _ensure_loaded()
            return _cache.get(str(guild_id), {}).get(self._full_key(key), default)

    def get_server(self, guild_id) -> dict:
        """Return all settings stored by this cog for a server (plain dict copy).

        Keys are returned WITHOUT the cog namespace prefix.
        """
        with _lock:
            _ensure_loaded()
            raw = _cache.get(str(guild_id), {})
            return {
                self._strip_ns(k): v
                for k, v in raw.items()
                if self._strip_ns(k) is not None
            }

    # ── Write ─────────────────────────────────────────────────────────────────

    def set(self, guild_id, key: str, value) -> bool:
        """Save a single setting. Persisted to the database immediately.

        Returns True if the value was successfully written to the database,
        False if all retry attempts failed (value is still updated in the
        local in-memory cache for the current session).

        Example usage in a command::

            if not cfg.set(guild.id, "welcome_channel", channel.id):
                await ctx.send("⚠️ Guardado en memoria pero no en la base de datos — "
                               "el cambio se perderá si el bot se reinicia.")
        """
        with _lock:
            _ensure_loaded()
            gid = str(guild_id)
            fk  = self._full_key(key)
            _cache.setdefault(gid, {})[fk] = value
            return _request_write("PUT", f"/{gid}/{fk}", {"value": value})

    def set_server(self, guild_id, config: dict) -> bool:
        """Replace ALL of this cog's settings for a server at once.

        Safe replace strategy: upsert new values FIRST, then remove stale
        old keys.  This ensures the previous config is never erased from the
        database before the new one is confirmed — a partial write failure
        leaves the old data intact rather than producing an empty config.

        Returns True if every write succeeded, False if any failed.
        """
        with _lock:
            _ensure_loaded()
            gid = str(guild_id)
            _cache.setdefault(gid, {})

            # Determine which old keys will be removed (keys no longer in config)
            new_fkeys = {self._full_key(k) for k in config}
            stale_fkeys = [
                fk for fk in list(_cache.get(gid, {}))
                if self._strip_ns(fk) is not None and fk not in new_fkeys
            ]

            ok = True

            # Step 1 — write new values first so DB is never empty during the op
            for k, v in config.items():
                fk = self._full_key(k)
                _cache[gid][fk] = v
                if not _request_write("PUT", f"/{gid}/{fk}", {"value": v}):
                    ok = False

            # Step 2 — only remove stale keys AFTER new values are confirmed
            for fk in stale_fkeys:
                _cache.get(gid, {}).pop(fk, None)
                if not _request_write("DELETE", f"/{gid}/{fk}"):
                    ok = False

            return ok

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, guild_id, key: str) -> bool:
        """Remove a single setting key for a server.

        Returns True if the database confirmed the deletion, False otherwise.
        """
        with _lock:
            _ensure_loaded()
            gid = str(guild_id)
            fk  = self._full_key(key)
            _cache.get(gid, {}).pop(fk, None)
            return _request_write("DELETE", f"/{gid}/{fk}")

    def clear_server(self, guild_id) -> bool:
        """Delete ALL of this cog's settings for a server.

        Returns True if the database confirmed the deletion, False otherwise.
        """
        with _lock:
            _ensure_loaded()
            gid = str(guild_id)
            if gid in _cache:
                for k in list(_cache[gid]):
                    if self._strip_ns(k) is not None:
                        del _cache[gid][k]
            return _request_write("DELETE", f"/{gid}?module={self._ns}")


# ── Legacy module-level functions (namespace = "_global") ─────────────────────
# These still work unchanged for older cogs.  New cogs should use ConfigManager.

_LEGACY = ConfigManager("_global")


def get(guild_id, key: str, default=None):
    """Legacy: get a setting from the shared ``_global`` namespace."""
    return _LEGACY.get(guild_id, key, default)


def set(guild_id, key: str, value) -> bool:
    """Legacy: save a setting into the shared ``_global`` namespace."""
    return _LEGACY.set(guild_id, key, value)


def delete(guild_id, key: str) -> bool:
    """Legacy: remove a setting from the shared ``_global`` namespace."""
    return _LEGACY.delete(guild_id, key)


def get_server(guild_id) -> dict:
    """Legacy: return all ``_global`` namespace settings for a server."""
    return _LEGACY.get_server(guild_id)


def set_server(guild_id, config: dict) -> bool:
    """Legacy: replace all ``_global`` namespace settings for a server."""
    return _LEGACY.set_server(guild_id, config)


def clear_server(guild_id) -> bool:
    """Legacy: delete all ``_global`` namespace settings for a server."""
    return _LEGACY.clear_server(guild_id)


def all_servers() -> dict:
    """Return a copy of the full raw cache keyed by guild_id string."""
    with _lock:
        _ensure_loaded()
        return dict(_cache)
'''

# ── main.py ───────────────────────────────────────────────────────────────────
MAIN_PY = '''\
"""
Discord Bot — auto-loads all cogs in the cogs/ directory.
Per-server configuration is persisted via config_manager.
"""
import os
import asyncio
import discord
from discord.ext import commands
from pathlib import Path

TOKEN  = os.environ.get("DISCORD_TOKEN")
PREFIX = os.environ.get("BOT_PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True   # Required for on_member_join / on_member_remove

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"\\u2705 Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"\\u2705 Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"\\u26a0\\ufe0f  Slash command sync failed: {e}")


async def load_cogs():
    cogs_dir = Path(__file__).parent / "cogs"
    if not cogs_dir.exists():
        print("\\u26a0\\ufe0f  No cogs/ directory found.")
        return
    for cog_file in sorted(cogs_dir.glob("*.py")):
        if cog_file.name.startswith("_"):
            continue
        ext = f"cogs.{cog_file.stem}"
        try:
            await bot.load_extension(ext)
            print(f"\\u2705 Loaded cog: {ext}")
        except Exception as e:
            print(f"\\u274c Failed to load {ext}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
'''

# ── cogs/ping.py ─────────────────────────────────────────────────────────────
PING_COG_PY = '''\
"""Example cog — ping/pong with prefix and slash command."""
import discord
from discord.ext import commands
from discord import app_commands


class Ping(commands.Cog):
    """Basic ping command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        """Prefix command: !ping"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"\\U0001f3d3 Pong! Latency: **{latency}ms**")

    @app_commands.command(name="ping", description="Check the bot latency")
    async def ping_slash(self, interaction: discord.Interaction):
        """Slash command: /ping"""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"\\U0001f3d3 Pong! Latency: **{latency}ms**", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
'''

# ── cogs/welcome.py ──────────────────────────────────────────────────────────
WELCOME_COG_PY = '''\
"""
Welcome & Goodbye System
Persistent per-server configuration via config_manager.
Configurations survive bot restarts — nothing is stored in memory.

Commands (admin only)
---------------------
  !setwelcome #channel [message]   Set the welcome channel + optional message
  !setgoodbye #channel [message]   Set the goodbye channel + optional message
  !welcometest                     Send a test welcome message
  !goodbyetest                     Send a test goodbye message
  !welcomeoff                      Disable welcome messages
  !goodbyeoff                      Disable goodbye messages
  !welcomeconfig                   Show current config

Message placeholders
--------------------
  {user}    — member username
  {mention} — @mention the member
  {server}  — server name
  {count}   — current member count
"""
import discord
from discord.ext import commands
from config_manager import ConfigManager

cfg = ConfigManager(__name__)   # namespace = "welcome" — isolated from other cogs

DEFAULT_WELCOME = "\\U0001f44b Welcome to **{server}**, {mention}! You are member **#{count}**."
DEFAULT_GOODBYE = "\\U0001f44b **{user}** has left **{server}**. We now have **{count}** members."


class Welcome(commands.Cog):
    """Welcome and goodbye messages with persistent configuration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _fmt(self, template: str, member: discord.Member) -> str:
        return template.format(
            user=member.name,
            mention=member.mention,
            server=member.guild.name,
            count=member.guild.member_count,
        )

    # ── Events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel_id = cfg.get(member.guild.id, "welcome_channel")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        msg = cfg.get(member.guild.id, "welcome_message") or DEFAULT_WELCOME
        try:
            await channel.send(self._fmt(msg, member))
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel_id = cfg.get(member.guild.id, "goodbye_channel")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        msg = cfg.get(member.guild.id, "goodbye_message") or DEFAULT_GOODBYE
        try:
            await channel.send(self._fmt(msg, member))
        except discord.Forbidden:
            pass

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name="setwelcome")
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx, channel: discord.TextChannel, *, message: str = None):
        """Set the welcome channel (and optional custom message)."""
        cfg.set(ctx.guild.id, "welcome_channel", channel.id)
        if message:
            cfg.set(ctx.guild.id, "welcome_message", message)
        msg = message or DEFAULT_WELCOME
        await ctx.send(
            f"\\u2705 Welcome channel set to {channel.mention}\\n"
            f"Message: `{msg}`\\n"
            f"Placeholders: `{{user}}` `{{mention}}` `{{server}}` `{{count}}`"
        )

    @commands.command(name="setgoodbye")
    @commands.has_permissions(administrator=True)
    async def set_goodbye(self, ctx, channel: discord.TextChannel, *, message: str = None):
        """Set the goodbye channel (and optional custom message)."""
        cfg.set(ctx.guild.id, "goodbye_channel", channel.id)
        if message:
            cfg.set(ctx.guild.id, "goodbye_message", message)
        msg = message or DEFAULT_GOODBYE
        await ctx.send(
            f"\\u2705 Goodbye channel set to {channel.mention}\\n"
            f"Message: `{msg}`"
        )

    @commands.command(name="welcomeoff")
    @commands.has_permissions(administrator=True)
    async def welcome_off(self, ctx):
        """Disable welcome messages for this server."""
        cfg.delete(ctx.guild.id, "welcome_channel")
        cfg.delete(ctx.guild.id, "welcome_message")
        await ctx.send("\\u2705 Welcome messages disabled.")

    @commands.command(name="goodbyeoff")
    @commands.has_permissions(administrator=True)
    async def goodbye_off(self, ctx):
        """Disable goodbye messages for this server."""
        cfg.delete(ctx.guild.id, "goodbye_channel")
        cfg.delete(ctx.guild.id, "goodbye_message")
        await ctx.send("\\u2705 Goodbye messages disabled.")

    @commands.command(name="welcometest")
    @commands.has_permissions(administrator=True)
    async def welcome_test(self, ctx):
        """Send a test welcome message to the configured channel."""
        channel_id = cfg.get(ctx.guild.id, "welcome_channel")
        if not channel_id:
            await ctx.send("\\u274c No welcome channel set. Use `!setwelcome #channel`.")
            return
        channel = ctx.guild.get_channel(int(channel_id))
        msg = cfg.get(ctx.guild.id, "welcome_message") or DEFAULT_WELCOME
        await channel.send(self._fmt(msg, ctx.author))
        await ctx.send(f"\\u2705 Test welcome sent to {channel.mention}.")

    @commands.command(name="goodbyetest")
    @commands.has_permissions(administrator=True)
    async def goodbye_test(self, ctx):
        """Send a test goodbye message to the configured channel."""
        channel_id = cfg.get(ctx.guild.id, "goodbye_channel")
        if not channel_id:
            await ctx.send("\\u274c No goodbye channel set. Use `!setgoodbye #channel`.")
            return
        channel = ctx.guild.get_channel(int(channel_id))
        msg = cfg.get(ctx.guild.id, "goodbye_message") or DEFAULT_GOODBYE
        await channel.send(self._fmt(msg, ctx.author))
        await ctx.send(f"\\u2705 Test goodbye sent to {channel.mention}.")

    @commands.command(name="welcomeconfig")
    @commands.has_permissions(administrator=True)
    async def welcome_config(self, ctx):
        """Show the current welcome/goodbye configuration."""
        w_ch  = cfg.get(ctx.guild.id, "welcome_channel")
        g_ch  = cfg.get(ctx.guild.id, "goodbye_channel")
        w_msg = cfg.get(ctx.guild.id, "welcome_message") or DEFAULT_WELCOME
        g_msg = cfg.get(ctx.guild.id, "goodbye_message") or DEFAULT_GOODBYE

        embed = discord.Embed(title="\\U0001f4cb Welcome & Goodbye Config", color=0x5865F2)
        embed.add_field(name="Welcome Channel",
                        value=f"<#{w_ch}>" if w_ch else "Not set", inline=True)
        embed.add_field(name="Goodbye Channel",
                        value=f"<#{g_ch}>" if g_ch else "Not set", inline=True)
        embed.add_field(name="\\u200b", value="\\u200b", inline=True)
        embed.add_field(name="Welcome Message", value=f"`{w_msg}`", inline=False)
        embed.add_field(name="Goodbye Message",  value=f"`{g_msg}`", inline=False)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
'''

# ── requirements.txt ──────────────────────────────────────────────────────────
REQUIREMENTS_TXT = "discord.py>=2.3.2\nboto3>=1.38.0\n"

# ── Files that are seeded (key = R2 path, value = (content, always_update)) ──
# always_update=True  → overwrite every time the panel starts (utility files)
# always_update=False → only upload when the file does not exist in R2 (user files)
DEFAULT_FILES: dict[str, tuple[str, bool]] = {
    "config_manager.py": (CONFIG_MANAGER_PY, True),   # always keep latest
    "main.py":           (MAIN_PY,           False),  # don't overwrite user's bot
    "cogs/ping.py":      (PING_COG_PY,       False),
    "cogs/welcome.py":   (WELCOME_COG_PY,    False),
    "requirements.txt":  (REQUIREMENTS_TXT,  False),
}
