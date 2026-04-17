import logging
import discord
from discord.ext import commands
import re
import os
import asyncpg # type: ignore
from typing import Optional

log = logging.getLogger(__name__)

# Regex to find custom emojis
CUSTOM_EMOJI_RE = re.compile(r"<a?:.+?:(\d+)>")

class EmojiTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def cog_load(self):
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            log.error("DATABASE_URL not found. Emoji tracking will fail.")
            return

        # Fix for hosted databases: 'postgres://' must be 'postgresql://' for asyncpg
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        try:
            self.pool = await asyncpg.create_pool(db_url)
            await self.create_table()
            log.info("Database connected and table verified.")
        except Exception as e:
            log.error("Failed to connect to database: %s", e)

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    async def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS emoji_stats (
            guild_id BIGINT,
            user_id BIGINT,
            emoji_id TEXT,
            is_reaction BOOLEAN,
            usage_count INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, user_id, emoji_id, is_reaction)
        );
        """
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(query)

    async def increment_usage(self, guild_id, user_id, emoji_id, is_reaction):
        if not self.pool:
            return

        query = """
        INSERT INTO emoji_stats (guild_id, user_id, emoji_id, is_reaction, usage_count)
        VALUES ($1, $2, $3, $4, 1)
        ON CONFLICT (guild_id, user_id, emoji_id, is_reaction)
        DO UPDATE SET usage_count = emoji_stats.usage_count + 1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, guild_id, user_id, emoji_id, is_reaction)

    def resolve_emoji(self, emoji_key):
        if emoji_key.isdigit():
            emoji_obj = self.bot.get_emoji(int(emoji_key))
            if emoji_obj:
                return str(emoji_obj)
            return f"[`🔗 Image`](https://cdn.discordapp.com/emojis/{emoji_key}.png)"
        return emoji_key

    # --- Event Listeners ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        emoji_ids = CUSTOM_EMOJI_RE.findall(message.content)
        if not emoji_ids:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        for emoji_id in emoji_ids:
            await self.increment_usage(guild_id, user_id, emoji_id, is_reaction=False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return

        guild_id = payload.guild_id
        user_id = payload.user_id

        emoji = payload.emoji
        emoji_key = str(emoji.id) if emoji.id else emoji.name

        await self.increment_usage(guild_id, user_id, emoji_key, is_reaction=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        pass

    # --- Commands ---

    @commands.group(name="emojistats", aliases=["es"], invoke_without_command=True)
    async def emoji_stats(self, ctx, target: Optional[discord.Member] = None):
        """Stats for messages."""
        await self.show_stats(ctx, target, is_reaction=False)

    @emoji_stats.command(name="reactions")
    async def reactions_stats(self, ctx, target: Optional[discord.Member] = None):
        """Stats for reactions."""
        await self.show_stats(ctx, target, is_reaction=True)

    async def show_stats(self, ctx, target, is_reaction):
        if not self.pool:
            return await ctx.send("Database not connected.")

        guild_id = ctx.guild.id

        if target:
            query = """
                SELECT emoji_id, usage_count FROM emoji_stats
                WHERE guild_id = $1 AND user_id = $2 AND is_reaction = $3
                ORDER BY usage_count DESC
                LIMIT 10;
            """
            args = (guild_id, target.id, is_reaction)
            title = f"👤 {target.display_name}'s {'Reaction' if is_reaction else 'Message'} Emojis"
        else:
            query = """
                SELECT emoji_id, SUM(usage_count) as total FROM emoji_stats
                WHERE guild_id = $1 AND is_reaction = $2
                GROUP BY emoji_id
                ORDER BY total DESC
                LIMIT 10;
            """
            args = (guild_id, is_reaction)
            title = f"📊 Server {'Reaction' if is_reaction else 'Message'} Emojis"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)

        if not rows:
            return await ctx.send("No stats recorded yet.")

        lines = []
        for i, row in enumerate(rows, 1):
            emoji_display = self.resolve_emoji(row['emoji_id'])
            count = row['usage_count'] if target else row['total']
            lines.append(f"**{i}.** {emoji_display} : {count}")

        embed = discord.Embed(title=title, description="\n".join(lines), color=discord.Color.gold())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EmojiTracker(bot))
