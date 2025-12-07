import discord
from discord.ext import commands
from typing import Optional
import json
import re
from operator import itemgetter
import os

# --- Configuration and Helper Functions ---
DATA_FILE = "data/emoji_stats.json" 
CUSTOM_EMOJI_RE = re.compile(r"<a?:.+?:(\d+)>")

def load_stats():
    """Reads the stats from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {DATA_FILE} is corrupted. Returning empty stats.")
        return {}

def save_stats(stats):
    """Writes the stats to the JSON file."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True) # Ensure data folder exists
    with open(DATA_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

class EmojiTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def resolve_emoji(self, guild, emoji_key):
        """Resolves an emoji key (ID or name) into a displayable string."""
        if emoji_key.isdigit():
            emoji_obj = guild.get_emoji(int(emoji_key))
            return str(emoji_obj) if emoji_obj else f"[Deleted ID: {emoji_key}]"
        else:
            return emoji_key

    # --- Event Listeners: Tracking ---

    @commands.Cog.listener()
    async def on_message(self, message):
        """Tracks custom emojis used directly in messages."""
        if message.author.bot or not message.guild:
            return

        stats = load_stats()
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        # Initialize full structure: messages, users, and reactions placeholders
        stats.setdefault(guild_id, {"messages": {"overall": {}, "users": {}}, 
                                    "reactions": {"overall": {}, "users": {}}})
        message_stats = stats[guild_id]["messages"]
        
        emoji_ids = CUSTOM_EMOJI_RE.findall(message.content)
        
        if not emoji_ids:
            save_stats(stats)
            return

        for emoji_id in emoji_ids:
            # 1. Update overall server usage
            message_stats["overall"][emoji_id] = message_stats["overall"].get(emoji_id, 0) + 1
            
            # 2. Update user-specific usage
            message_stats["users"].setdefault(user_id, {})
            message_stats["users"][user_id][emoji_id] = message_stats["users"][user_id].get(emoji_id, 0) + 1

        save_stats(stats)
            
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Tracks emojis used as reactions (adds)."""
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return

        stats = load_stats()
        guild_id = str(payload.guild_id)
        user_id = str(payload.user_id)
        
        # Determine the emoji key (ID for custom, name for unicode)
        emoji = payload.emoji
        emoji_key = str(emoji.id) if emoji.id else emoji.name

        stats.setdefault(guild_id, {"messages": {"overall": {}, "users": {}}, 
                                    "reactions": {"overall": {}, "users": {}}})
        reaction_stats = stats[guild_id]["reactions"]

        # 1. Update overall reaction count
        reaction_stats["overall"][emoji_key] = reaction_stats["overall"].get(emoji_key, 0) + 1

        # 2. Update user-specific reaction count
        reaction_stats["users"].setdefault(user_id, {})
        reaction_stats["users"][user_id][emoji_key] = reaction_stats["users"][user_id].get(emoji_key, 0) + 1

        save_stats(stats)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Tracks emojis used as reactions (removals)."""
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return

        stats = load_stats()
        guild_id = str(payload.guild_id)
        user_id = str(payload.user_id)
        
        if guild_id not in stats or "reactions" not in stats[guild_id]:
            return

        emoji = payload.emoji
        emoji_key = str(emoji.id) if emoji.id else emoji.name
        reaction_stats = stats[guild_id]["reactions"]
        user_reaction_stats = reaction_stats["users"].get(user_id, {})

        # Decrement and clean up overall count
        if reaction_stats["overall"].get(emoji_key, 0) > 0:
            reaction_stats["overall"][emoji_key] -= 1
            if reaction_stats["overall"][emoji_key] == 0:
                del reaction_stats["overall"][emoji_key]

        # Decrement and clean up user count
        if user_reaction_stats.get(emoji_key, 0) > 0:
            user_reaction_stats[emoji_key] -= 1
            if user_reaction_stats[emoji_key] == 0:
                del user_reaction_stats[emoji_key]
                if not user_reaction_stats:
                    del reaction_stats["users"][user_id]
            
        save_stats(stats)
    
    # --- Commands: Displaying Statistics ---
    @commands.group(name="emojistats", aliases=["es"], invoke_without_command=True)
    async def emoji_stats(self, ctx, target: Optional[discord.Member] = None):
        """Displays message emoji usage (Overall or for a specific user)."""
        if target is None:
            await self._display_stats(ctx, "messages", "overall")
        else:
            await self._display_stats(ctx, "messages", "user", target)
    @emoji_stats.command(name="reactions")
    async def reactions_stats(self, ctx, target: Optional[discord.Member] = None):
        """Displays emoji reaction statistics (Overall or for a specific user)."""
        if target is None:
            await self._display_stats(ctx, "reactions", "overall")
        else:
            await self._display_stats(ctx, "reactions", "user", target)


    async def _display_stats(self, ctx, category: str, scope: str, target: Optional[discord.Member] = None):
        """Internal function to handle all display logic."""
        stats = load_stats()
        guild_id = str(ctx.guild.id)
        
        if guild_id not in stats:
            return await ctx.send("No emoji usage has been recorded yet.")

        source = stats[guild_id].get(category, {})
        
        if scope == "overall":
            data_to_display = source.get("overall", {})
            title_scope = "Server Overall"
        else:
            if target is None:
                return await ctx.send("Please specify a user.")
            user_id = str(target.id)
            data_to_display = source.get("users", {}).get(user_id, {})
            title_scope = f"{target.display_name}'s"
            
        title_category = "Message Emoji" if category == "messages" else "Reaction Emoji"
        title = f"📊 {title_scope} {title_category} Usage"

        if not data_to_display:
            await ctx.send(f"No {category} usage recorded for {title_scope.lower()}.")
            return

        sorted_stats = sorted(data_to_display.items(), key=itemgetter(1), reverse=True)[:10]

        response = []
        for rank, (emoji_key, count) in enumerate(sorted_stats, start=1):
            emoji_display = self.resolve_emoji(ctx.guild, emoji_key)
            response.append(f"**{rank}. {emoji_display}**: {count} uses")
            
        embed = discord.Embed(
            title=title,
            description="\n".join(response),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EmojiTracker(bot))