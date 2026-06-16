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

# Configuration
KEKW_EMOJI_NAME_PATTERN = "kekw"  # matches emoji names starting with this (case-insensitive)
KEKW_RESTRICTED_ROLE_NAME = "is poor"  # role name that blocks kekw usage

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
            await self.create_received_table()
            log.info("Database connected and tables verified.")
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
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def create_received_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS reaction_received_stats (
            guild_id BIGINT,
            recipient_id BIGINT,
            emoji_name TEXT,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, recipient_id, emoji_name)
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def get_kekw_balance(self, guild_id, user_id):
        """Get a user's net kekw balance from reaction_received_stats."""
        if not self.pool:
            return 0
        query = """
        SELECT COALESCE(SUM(count), 0) as total
        FROM reaction_received_stats
        WHERE guild_id = $1 AND recipient_id = $2 AND emoji_name ILIKE 'kekw%';
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, guild_id, user_id)
        return row['total'] if row else 0

    async def decrement_received(self, guild_id, user_id, emoji_name):
        """Decrement a user's received count (costs them to use kekw)."""
        if not self.pool:
            return
        query = """
        INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
        VALUES ($1, $2, $3, -1)
        ON CONFLICT (guild_id, recipient_id, emoji_name)
        DO UPDATE SET count = reaction_received_stats.count - 1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, guild_id, user_id, emoji_name)

    async def enforce_kekw_role(self, guild, member):
        """Add or remove the kekw restricted role based on kekwboard balance."""
        role = discord.utils.get(guild.roles, name=KEKW_RESTRICTED_ROLE_NAME)
        if not role:
            return  # Role doesn't exist yet, skip

        balance = await self.get_kekw_balance(guild.id, member.id)
        try:
            if balance <= 0 and role not in member.roles:
                await member.add_roles(role, reason="kekw balance hit 0")
                log.info("Added kekw restricted role to %s (balance: %d)", member, balance)
            elif balance > 0 and role in member.roles:
                await member.remove_roles(role, reason="kekw balance above 0")
                log.info("Removed kekw restricted role from %s (balance: %d)", member, balance)
        except discord.Forbidden:
            log.warning("Missing permissions to manage roles for %s", member)

    def is_kekw_emoji(self, emoji):
        """Check if an emoji matches the kekw pattern."""
        if emoji.name and emoji.name.lower().startswith(KEKW_EMOJI_NAME_PATTERN):
            return True
        return False

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

    async def increment_received(self, guild_id, recipient_id, emoji_name):
        if not self.pool:
            return

        query = """
        INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
        VALUES ($1, $2, $3, 1)
        ON CONFLICT (guild_id, recipient_id, emoji_name)
        DO UPDATE SET count = reaction_received_stats.count + 1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, guild_id, recipient_id, emoji_name)

    def resolve_emoji(self, emoji_key):
        if emoji_key.isdigit():
            emoji_obj = self.bot.get_emoji(int(emoji_key))
            if emoji_obj:
                return str(emoji_obj)
            return f"[`🔗 Image`](https://cdn.discordapp.com/emojis/{emoji_key}.png)"
        return emoji_key

    # --- Event Listeners ---

    @commands.Cog.listener()
    async def on_ready(self):
        """Configure kekw emoji restrictions on startup."""
        if not self.pool:
            return
        for guild in self.bot.guilds:
            # Create the restricted role if it doesn't exist
            restricted_role = discord.utils.get(guild.roles, name=KEKW_RESTRICTED_ROLE_NAME)
            if not restricted_role:
                try:
                    restricted_role = await guild.create_role(
                        name=KEKW_RESTRICTED_ROLE_NAME,
                        reason="Auto-created for kekw economy"
                    )
                    log.info("Created '%s' role in %s", KEKW_RESTRICTED_ROLE_NAME, guild.name)
                except discord.Forbidden:
                    log.warning("Missing permissions to create role in %s", guild.name)
                    continue



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

        # Track who received the reaction (for leaderboards like !kekwboard)
        if emoji.name:
            channel = self.bot.get_channel(payload.channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(payload.message_id)
                    if not message.author.bot:
                        # Skip self-reactions for kekw economy
                        if self.is_kekw_emoji(emoji) and message.author.id == user_id:
                            return

                        # Block kekw usage if reactor has "is poor" role
                        if self.is_kekw_emoji(emoji):
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                reactor = guild.get_member(user_id)
                                if reactor:
                                    role = discord.utils.get(guild.roles, name=KEKW_RESTRICTED_ROLE_NAME)
                                    if role and role in reactor.roles:
                                        # Remove the reaction and bail
                                        try:
                                            await message.remove_reaction(emoji, reactor)
                                        except discord.Forbidden:
                                            pass
                                        return

                        await self.increment_received(guild_id, message.author.id, emoji.name)

                        # --- Kekw balance logic ---
                        if self.is_kekw_emoji(emoji):
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                # Decrement the reactor's balance (costs them to use kekw)
                                reactor = guild.get_member(user_id)
                                if reactor and not reactor.bot:
                                    await self.decrement_received(guild_id, user_id, emoji.name)
                                    await self.enforce_kekw_role(guild, reactor)

                                # Recipient just got +1 from increment_received above, update their role
                                recipient = guild.get_member(message.author.id)
                                if recipient and not recipient.bot:
                                    await self.enforce_kekw_role(guild, recipient)

                except (discord.NotFound, discord.Forbidden):
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return

        guild_id = payload.guild_id
        user_id = payload.user_id
        emoji = payload.emoji

        if not emoji.name:
            return

        # Only process kekw removals
        if not self.is_kekw_emoji(emoji):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
            if message.author.bot:
                return

            # Skip self-reaction removals
            if message.author.id == user_id:
                return

            # Refund the reactor (+1 back to their balance)
            guild = self.bot.get_guild(guild_id)
            if guild:
                reactor = guild.get_member(user_id)
                if reactor and not reactor.bot:
                    await self.increment_received(guild_id, user_id, emoji.name)
                    await self.enforce_kekw_role(guild, reactor)

                # Deduct from the recipient (-1 since they lost the kekw)
                recipient = guild.get_member(message.author.id)
                if recipient and not recipient.bot:
                    await self.decrement_received(guild_id, message.author.id, emoji.name)
                    await self.enforce_kekw_role(guild, recipient)

        except (discord.NotFound, discord.Forbidden):
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

    @commands.command(name="kekwboard")
    async def kekwboard(self, ctx):
        """Ranks users by how many kekw reactions they've received."""
        if not self.pool:
            return await ctx.send("Database not connected.")

        query = """
            SELECT recipient_id, SUM(count) as total
            FROM reaction_received_stats
            WHERE guild_id = $1 AND emoji_name ILIKE 'kekw%'
            GROUP BY recipient_id
            ORDER BY total DESC
            LIMIT 10;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, ctx.guild.id)

        if not rows:
            return await ctx.send("No kekw reactions tracked yet.")

        lines = []
        for i, row in enumerate(rows, 1):
            member = ctx.guild.get_member(row['recipient_id'])
            name = member.display_name if member else f"<@{row['recipient_id']}>"
            lines.append(f"**{i}.** {name} — {row['total']}")

        embed = discord.Embed(
            title="KEKW Leaderboard",
            description="\n".join(lines),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @commands.command(name="kekwscore")
    async def kekwscore(self, ctx, target: Optional[discord.Member] = None):
        """Check your kekw balance (or someone else's). 0 = restricted from using kekw."""
        if not self.pool:
            return await ctx.send("Database not connected.")

        member = target or ctx.author
        balance = await self.get_kekw_balance(ctx.guild.id, member.id)

        role = discord.utils.get(ctx.guild.roles, name=KEKW_RESTRICTED_ROLE_NAME)
        restricted = role in member.roles if role else False

        status = "🚫 RESTRICTED" if restricted else "✅ Can use kekw"
        embed = discord.Embed(
            title=f"KEKW Balance — {member.display_name}",
            description=f"**Balance:** {balance}\n**Status:** {status}",
            color=discord.Color.red() if restricted else discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="kekwmint", hidden=True)
    async def kekwmint(self, ctx, target: discord.Member, amount: int = 1):
        """Mint kekws into a user's balance. Tangster/Centerist role only."""
        MINT_ROLE_IDS = {1071629030408847371, 1071861949752676372}
        if not any(r.id in MINT_ROLE_IDS for r in ctx.author.roles):
            return  # Silently ignore

        if not self.pool:
            return

        query = """
        INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
        VALUES ($1, $2, 'kekw_mint', $3)
        ON CONFLICT (guild_id, recipient_id, emoji_name)
        DO UPDATE SET count = reaction_received_stats.count + $3;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, ctx.guild.id, target.id, amount)

        # Enforce role in case they were restricted
        await self.enforce_kekw_role(ctx.guild, target)

        # Delete the command message to hide it
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command(name="poors")
    async def poors(self, ctx):
        """Show everyone with 0 or fewer kekws, poorest first."""
        if not self.pool:
            return await ctx.send("Database not connected.")

        query = """
        SELECT recipient_id, SUM(count) as balance
        FROM reaction_received_stats
        WHERE guild_id = $1 AND emoji_name ILIKE 'kekw%'
        GROUP BY recipient_id
        HAVING SUM(count) <= 0
        ORDER BY balance ASC;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, ctx.guild.id)

        if not rows:
            return await ctx.send("No poors found. Everyone is rich in kekws.")

        lines = []
        for i, row in enumerate(rows, 1):
            member = ctx.guild.get_member(row['recipient_id'])
            name = member.display_name if member else f"Unknown ({row['recipient_id']})"
            lines.append(f"{i}. **{name}** — {row['balance']} kekws")

        embed = discord.Embed(
            title="💸 The Poors",
            description="\n".join(lines),
            color=discord.Color.dark_grey()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EmojiTracker(bot))
