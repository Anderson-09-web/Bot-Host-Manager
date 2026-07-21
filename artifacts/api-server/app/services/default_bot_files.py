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
Saves everything to a single server_configs.json, synced to Cloudflare R2.
Configurations survive bot restarts, file edits, and updates.

Usage
-----
    import config_manager as cfg

    # Read a value (returns None if not set)
    channel_id = cfg.get(guild.id, "welcome_channel")

    # Save a value (auto-syncs to R2)
    cfg.set(guild.id, "welcome_channel", channel.id)
    cfg.set(guild.id, "welcome_message", "Welcome {mention} to {server}!")

    # Delete a single key
    cfg.delete(guild.id, "welcome_channel")

    # Get all settings for a server
    server_settings = cfg.get_server(guild.id)   # returns a dict copy

    # Replace all settings for a server at once
    cfg.set_server(guild.id, {"welcome_channel": 123, "prefix": "!"})

    # Remove all settings for a server
    cfg.clear_server(guild.id)

JSON structure of server_configs.json
--------------------------------------
{
  "123456789": {            <- guild_id (always stored as string)
    "welcome_channel": 987654321,
    "welcome_message": "Welcome {mention}!",
    "goodbye_channel": 111222333,
    "log_channel": 444555666,
    ...
  },
  "999888777": { ... }
}
"""

import json
import os
import threading
import boto3
from pathlib import Path

# ── File path ─────────────────────────────────────────────────────────────────
_CONFIG_FILE = Path(__file__).parent / "server_configs.json"

# ── In-memory cache + thread lock ─────────────────────────────────────────────
_lock = threading.Lock()
_data: dict = {}
_loaded = False


# ── Internal ──────────────────────────────────────────────────────────────────

def _load_from_disk() -> dict:
    """Read the JSON config from disk. Returns {} on any error."""
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[config_manager] Warning: could not parse config file: {e}", flush=True)
    return {}


def _ensure_loaded():
    """Lazy-load from disk on first access."""
    global _data, _loaded
    if not _loaded:
        _data = _load_from_disk()
        _loaded = True
        total = len(_data)
        print(f"[config_manager] Loaded config for {total} server(s).", flush=True)


def _save():
    """Write to disk, then upload to R2."""
    text = json.dumps(_data, indent=2, ensure_ascii=False)
    try:
        _CONFIG_FILE.write_text(text, encoding="utf-8")
    except Exception as e:
        print(f"[config_manager] Warning: disk write failed: {e}", flush=True)
    _upload_to_r2(text.encode("utf-8"))


def _upload_to_r2(data: bytes):
    """
    Upload server_configs.json to R2 so it persists across restarts.
    Credentials come from the env vars injected by the hosting panel.
    Failures are logged but never raised.
    """
    endpoint = os.getenv("R2_ENDPOINT_URL")
    key_id   = os.getenv("R2_ACCESS_KEY_ID")
    secret   = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket   = os.getenv("R2_BUCKET_NAME")

    if not all([endpoint, key_id, secret, bucket]):
        return  # Running locally without R2 — skip silently

    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name="auto",
        )
        client.put_object(
            Bucket=bucket,
            Key="server_configs.json",
            Body=data,
            ContentType="application/json",
        )
    except Exception as e:
        print(
            f"[config_manager] Warning: R2 sync failed (config IS saved locally): {e}",
            flush=True,
        )


# ── Public API ────────────────────────────────────────────────────────────────

def get(guild_id, key: str, default=None):
    """
    Get a single setting for a server.

    Parameters
    ----------
    guild_id : int | str  — Discord guild ID
    key      : str        — setting name (e.g. "welcome_channel")
    default              — value returned when the key is not set

    Returns the stored value, or `default` if not found.
    """
    with _lock:
        _ensure_loaded()
        return _data.get(str(guild_id), {}).get(key, default)


def set(guild_id, key: str, value):
    """
    Save a single setting for a server. Persists to disk + R2 immediately.

    Parameters
    ----------
    guild_id : int | str       — Discord guild ID
    key      : str             — setting name
    value    : any JSON type   — str, int, bool, list, dict, or None
    """
    with _lock:
        _ensure_loaded()
        gid = str(guild_id)
        if gid not in _data:
            _data[gid] = {}
        _data[gid][key] = value
        _save()


def delete(guild_id, key: str):
    """Remove a single setting key for a server."""
    with _lock:
        _ensure_loaded()
        gid = str(guild_id)
        if gid in _data and key in _data[gid]:
            del _data[gid][key]
            _save()


def get_server(guild_id) -> dict:
    """
    Return all settings for a server as a plain dict copy.
    Modifying the returned dict does NOT save anything.
    """
    with _lock:
        _ensure_loaded()
        return dict(_data.get(str(guild_id), {}))


def set_server(guild_id, config: dict):
    """Replace ALL settings for a server at once. Persists immediately."""
    with _lock:
        _ensure_loaded()
        _data[str(guild_id)] = dict(config)
        _save()


def clear_server(guild_id):
    """Delete ALL settings for a server."""
    with _lock:
        _ensure_loaded()
        gid = str(guild_id)
        if gid in _data:
            del _data[gid]
            _save()


def all_servers() -> dict:
    """Return a copy of the full config dict keyed by guild_id string."""
    with _lock:
        _ensure_loaded()
        return dict(_data)
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
import config_manager as cfg

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
