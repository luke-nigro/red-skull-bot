import logging
import discord
from discord import app_commands
from discord.ext import commands
import re
import os
import asyncpg # type: ignore
from typing import Optional

log = logging.getLogger(__name__)

# Regex to find custom emojis
CUSTOM_EMOJI_RE = re.compile(r"<a?:.+?:(\d+)>")

# Configuration
KEKW_RESTRICTED_ROLE_NAME = "is poor"  # role name that blocks kekw usage

class EmojiTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        # In-memory cache: {guild_id: {emoji_id: group_name}}
        self._economy_emojis = {}

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
            await self.create_economy_emojis_table()
            await self.migrate_kekw_balances()
            await self.load_economy_emojis()
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

    async def create_economy_emojis_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS economy_emojis (
            guild_id BIGINT,
            emoji_id BIGINT,
            group_name TEXT NOT NULL DEFAULT 'kekw',
            PRIMARY KEY (guild_id, emoji_id)
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def load_economy_emojis(self):
        """Load all registered economy emojis into memory."""
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT guild_id, emoji_id, group_name FROM economy_emojis")
        self._economy_emojis = {}
        for row in rows:
            guild_id = row['guild_id']
            if guild_id not in self._economy_emojis:
                self._economy_emojis[guild_id] = {}
            self._economy_emojis[guild_id][row['emoji_id']] = row['group_name']

    async def migrate_kekw_balances(self):
        """One-time migration: consolidate old kekw% entries into a single 'kekw' row per user."""
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            # Check if there are any old-style entries to migrate
            check = await conn.fetchval(
                "SELECT COUNT(*) FROM reaction_received_stats WHERE emoji_name ILIKE 'kekw%' AND emoji_name != 'kekw'"
            )
            if not check:
                return

            # Consolidate: sum all kekw% rows per (guild_id, recipient_id) into the 'kekw' row
            await conn.execute("""
                INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
                SELECT guild_id, recipient_id, 'kekw', SUM(count)
                FROM reaction_received_stats
                WHERE emoji_name ILIKE 'kekw%'
                GROUP BY guild_id, recipient_id
                ON CONFLICT (guild_id, recipient_id, emoji_name)
                DO UPDATE SET count = EXCLUDED.count;
            """)

            # Delete the old fragmented rows
            await conn.execute(
                "DELETE FROM reaction_received_stats WHERE emoji_name ILIKE 'kekw%' AND emoji_name != 'kekw'"
            )
            log.info("Migrated %d old kekw entries into consolidated 'kekw' balances", check)

    async def get_kekw_balance(self, guild_id, user_id):
        """Get a user's net kekw balance from reaction_received_stats."""
        if not self.pool:
            return 0
        query = """
        SELECT COALESCE(SUM(count), 0) as total
        FROM reaction_received_stats
        WHERE guild_id = $1 AND recipient_id = $2 AND emoji_name = 'kekw';
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, guild_id, user_id)
        return row['total'] if row else 0

    async def decrement_received(self, guild_id, user_id, group_name):
        """Decrement a user's balance for a group (costs them to use the emoji)."""
        if not self.pool:
            return
        query = """
        INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
        VALUES ($1, $2, $3, -1)
        ON CONFLICT (guild_id, recipient_id, emoji_name)
        DO UPDATE SET count = reaction_received_stats.count - 1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, guild_id, user_id, group_name)

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

    def is_economy_emoji(self, guild_id, emoji):
        """Check if an emoji is registered in the economy. Returns group_name or None."""
        if not emoji.id:
            return None
        guild_emojis = self._economy_emojis.get(guild_id, {})
        return guild_emojis.get(emoji.id)

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

            # Sync slash commands to this guild (instant)
            try:
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                log.info("Slash commands synced to %s", guild.name)
            except Exception as e:
                log.warning("Failed to sync slash commands to %s: %s", guild.name, e)

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
                        group_name = self.is_economy_emoji(guild_id, emoji)

                        # Skip self-reactions for economy emojis
                        if group_name and message.author.id == user_id:
                            return

                        # Block economy emoji usage if reactor has "is poor" role
                        if group_name:
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

                        # --- Economy balance logic ---
                        if group_name:
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                # Decrement the reactor's balance (costs them to use the emoji)
                                reactor = guild.get_member(user_id)
                                if reactor and not reactor.bot:
                                    await self.decrement_received(guild_id, user_id, group_name)
                                    await self.enforce_kekw_role(guild, reactor)

                                # Recipient balance handled by increment_received above
                                # (emoji.name stored separately; group_name credit only if name != group)
                                recipient = guild.get_member(message.author.id)
                                if recipient and not recipient.bot:
                                    if emoji.name != group_name:
                                        await self.increment_received(guild_id, message.author.id, group_name)
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

        # Only process economy emoji removals
        group_name = self.is_economy_emoji(guild_id, emoji)
        if not group_name:
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
                    await self.increment_received(guild_id, user_id, group_name)
                    await self.enforce_kekw_role(guild, reactor)

                # Deduct from the recipient (-1 since they lost the emoji)
                recipient = guild.get_member(message.author.id)
                if recipient and not recipient.bot:
                    await self.decrement_received(guild_id, message.author.id, group_name)
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
            WHERE guild_id = $1 AND emoji_name = 'kekw'
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
    async def kekwmint_prefix(self, ctx):
        """Disabled - use /kekwmint instead."""
        pass

    @app_commands.command(name="kekwmint", description="Mint kekws into a user's balance")
    @app_commands.describe(target="User to mint kekws for", amount="Amount to mint (default 1)")
    async def kekwmint(self, interaction: discord.Interaction, target: discord.Member, amount: int = 1):
        MINT_ROLE_IDS = {1071629030408847371, 1071861949752676372}
        if not any(r.id in MINT_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        if not self.pool:
            return await interaction.response.send_message("DB not connected.", ephemeral=True)

        query = """
        INSERT INTO reaction_received_stats (guild_id, recipient_id, emoji_name, count)
        VALUES ($1, $2, 'kekw', $3)
        ON CONFLICT (guild_id, recipient_id, emoji_name)
        DO UPDATE SET count = reaction_received_stats.count + $3;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, interaction.guild.id, target.id, amount)

        await self.enforce_kekw_role(interaction.guild, target)
        await interaction.response.send_message(f"Minted {amount} kekws for {target.display_name}", ephemeral=True)

    @app_commands.command(name="kekwregister", description="Register an emoji as an economy emoji")
    @app_commands.describe(emoji_id="The emoji ID to register", group_name="Economy group (default: kekw)")
    async def kekwregister(self, interaction: discord.Interaction, emoji_id: str, group_name: str = "kekw"):
        MINT_ROLE_IDS = {1071629030408847371, 1071861949752676372}
        if not any(r.id in MINT_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        if not self.pool:
            return await interaction.response.send_message("DB not connected.", ephemeral=True)

        # Parse emoji ID from string (supports raw ID or <:name:id> format)
        match = re.search(r'(\d+)', emoji_id)
        if not match:
            return await interaction.response.send_message("Invalid emoji. Provide the emoji or its ID.", ephemeral=True)
        eid = int(match.group(1))

        query = """
        INSERT INTO economy_emojis (guild_id, emoji_id, group_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, emoji_id)
        DO UPDATE SET group_name = $3;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, interaction.guild.id, eid, group_name)

        if interaction.guild.id not in self._economy_emojis:
            self._economy_emojis[interaction.guild.id] = {}
        self._economy_emojis[interaction.guild.id][eid] = group_name

        emoji_obj = self.bot.get_emoji(eid)
        display = str(emoji_obj) if emoji_obj else f"ID {eid}"
        await interaction.response.send_message(f"✅ Registered {display} as economy emoji (group: `{group_name}`)", ephemeral=True)

    @app_commands.command(name="kekwunregister", description="Unregister an emoji from the economy")
    @app_commands.describe(emoji_id="The emoji ID to unregister")
    async def kekwunregister(self, interaction: discord.Interaction, emoji_id: str):
        MINT_ROLE_IDS = {1071629030408847371, 1071861949752676372}
        if not any(r.id in MINT_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        if not self.pool:
            return await interaction.response.send_message("DB not connected.", ephemeral=True)

        match = re.search(r'(\d+)', emoji_id)
        if not match:
            return await interaction.response.send_message("Invalid emoji. Provide the emoji or its ID.", ephemeral=True)
        eid = int(match.group(1))

        query = "DELETE FROM economy_emojis WHERE guild_id = $1 AND emoji_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(query, interaction.guild.id, eid)

        guild_emojis = self._economy_emojis.get(interaction.guild.id, {})
        guild_emojis.pop(eid, None)

        await interaction.response.send_message(f"❌ Unregistered emoji ID {eid} from economy", ephemeral=True)

    @app_commands.command(name="taxes", description="Decrement everyone's kekw balance")
    @app_commands.describe(amount="Amount to tax (default 1)")
    async def taxes(self, interaction: discord.Interaction, amount: int = 1):
        MINT_ROLE_IDS = {1071629030408847371, 1071861949752676372}
        if not any(r.id in MINT_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        if not self.pool:
            return await interaction.response.send_message("DB not connected.", ephemeral=True)

        query = """
        UPDATE reaction_received_stats
        SET count = count - $2
        WHERE guild_id = $1 AND emoji_name = 'kekw';
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, interaction.guild.id, amount)

        await interaction.response.send_message(f"💀 Taxed everyone {amount} kekws", ephemeral=True)

        # Enforce roles for anyone who just went to 0 or below
        for member in interaction.guild.members:
            if member.bot:
                continue
            await self.enforce_kekw_role(interaction.guild, member)

    @commands.command(name="poors")
    async def poors(self, ctx):
        """Show everyone with 0 or fewer kekws, poorest first."""
        if not self.pool:
            return await ctx.send("Database not connected.")

        query = """
        SELECT recipient_id, SUM(count) as balance
        FROM reaction_received_stats
        WHERE guild_id = $1 AND emoji_name = 'kekw'
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
