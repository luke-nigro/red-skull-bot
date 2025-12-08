import os
import random
from dotenv import load_dotenv
import discord
from discord import Embed
from discord.ext import commands
import aiohttp  # Add this import for HTTP requests
from aiohttp import web

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    raise ValueError('DISCORD_TOKEN environment variable is not set')
embed = Embed()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.command(name='skull')
async def on_skull_command(message):
    await message.send('Leave Red Skull alone, please. I beg of you.')

@bot.command(name='cringe')
async def on_cringe_command(message):
    await message.send('day')

@bot.command(name='bonk')
async def on_bonk_command(message):
    await message.send('https://media2.giphy.com/avatars/DogeBONK/coZ41g2NwRFS.gif')

@bot.command(name='ban')
async def on_ban_command(message, *, arg):
    await message.send(f'User {arg} has been permanently banned from the server, what a loser! <:day:1072575755256598559>')

@bot.command(name='boc')
async def on_boc_command(message):
    await message.send("Claude told me you are wrong and that I am very smart. Trump is right about everything. My homeschooled kids will be totally normal.")

@bot.command(name='squash')
async def on_squash_command(message):
    await message.send("Yeah man I'm going to need you to go ahead and calm down for me. Can you do that?")

@bot.command(name='hastings')
async def on_hastings_command(message):
    await message.send("https://cdn.discordapp.com/attachments/1072494728492359732/1367960843660165200/8kxnz2icgq131.png?ex=68167c50&is=68152ad0&hm=2919a9cba02febadf631d53dd4ab50e1eb5a01f381c12a1cd8f67c13d42ec5c2&")

@bot.command(name='kwiji')
async def on_kwiji_command(message):
    await message.send("Your favorite ~~closeted Catholic boy~~ priest main!")

@bot.command(name='e10din')
async def on_e10din_command(message):
    await message.send("https://cdn.discordapp.com/attachments/1072494728492359732/1368008973973852170/IMG_5306.jpg?ex=6816a923&is=681557a3&hm=00904f1d19b05ea742279044e907915bd91834cc34260289c2f3f68f98985128&")

@bot.command(name='pOK')
async def on_pok_command(message):
    await message.send("If you haven't heard already, he died in a terrible accident. He was trying to get a picture of his dog Kuma and he slipped on a banana peel and fell onto a cactus directly on his... well you know. He was in the hospital for a few days but he didn't make it. He was only 32 years old. He was a great guy and he will be missed.")

@bot.command(name='formande')
async def on_formande_command(message):
    await message.send("https://cdn.discordapp.com/attachments/1073304255567515648/1447648151723966736/image.png?ex=693862e7&is=69371167&hm=1633638b7c1834496f8ab4424ae28888a6273a52efe1eb49df2b35bace5ef50f&")

# Blue footed boobies
@bot.command(name='boobies')
async def on_boobies_command(message):
    await message.send("https://images.newscientist.com/wp-content/uploads/2014/05/dn25505-1_800.jpg")

@bot.command(name='roll')
async def on_roll_command(message, *, arg):
    if not arg.isdigit():
        await message.send("That's not a number you moron, pick a different number")
    elif int(arg) < 1:
        await message.send("Pick a number greater than 1 you moron")
    else:
        roll = random.randint(1, int(arg))
        await message.send(f"You rolled a {roll}.")

@bot.command(name='meme')
async def on_meme_command(message):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://meme-api.com/gimme') as response:
            if response.status == 200:
                data = await response.json()
                await message.send(data['url'])
            else:
                await message.send("Couldn't fetch a meme, and that's probably for the best tbh.")

@bot.command(name='cat')
async def on_cat_command(message):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.thecatapi.com/v1/images/search') as response:
            if response.status == 200:
                data = await response.json()
                await message.send(data[0]['url'])
            else:
                await message.send("The cat distribution system did not choose you today.")

@bot.command(name='dog')
async def on_dog_command(message):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://dog.ceo/api/breeds/image/random') as response:
            if response.status == 200:
                data = await response.json()
                await message.send(data['message'])
            else:
                await message.send("No dogs for you, this probably means you're a terrible person.")

async def health_check(request):
    return web.Response(text="Bot is alive!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render provides the PORT variable. Default to 8080 if not found.
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🔗 Web server started on port {port}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
        
    # --- START THE FAKE WEB SERVER FOR RENDER ---
    # This prevents the "Port scan timeout" error
    bot.loop.create_task(start_server()) 
    # --------------------------------------------

    # Load the new emoji tracking cog
    try:
        await bot.load_extension('cogs.emoji_tracker')
        print("Successfully loaded EmojiTracker cog.")
    except commands.ExtensionAlreadyLoaded:
        pass 
    except Exception as e:
        print(f"Failed to load EmojiTracker cog: {e}")

@bot.event
async def on_message(message):
    # 1. Prevent infinite loops (bot replying to itself)
    if message.author == bot.user:
        return

    # 2. Process Commands FIRST (so !skull, !ban etc work)
    await bot.process_commands(message)

    # 3. Custom Logic
    content_lower = message.content.lower()

    # Logic A: Cringe Check
    if 'cringe' in content_lower:
        roll = random.randint(1, 100)
        if roll == 1:
            await message.reply("you're cringe bro")

    # Logic B: Cheney Check
    if 'cheney' in content_lower:
        await message.reply("Shut up you idiot that's not why the Dems lost the election.")

bot.run(TOKEN)