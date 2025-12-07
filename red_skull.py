import os
import random
from dotenv import load_dotenv
import discord
from discord import Embed
from discord.ext import commands
import aiohttp  # Add this import for HTTP requests

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

@bot.event
async def on_cringe_message(message):
    await bot.process_commands(message)
    if 'cringe' in message.content.lower():
        roll = random.randint(1, 100)
        if roll == 1:
            await message.reply("you're cringe bro")

@bot.event
async def on_cheney_message(message):
    await bot.process_commands(message)
    if 'cheney' in message.content.lower():
        await message.reply("Shut up you idiot that’s not why the Dems lost the election.")

@bot.event
async def on_ready():
    # This is the ideal place to ensure cogs are loaded only once after connection.
    print(f'Logged in as {bot.user}')
    
    # Load the new emoji tracking cog
    try:
        await bot.load_extension('cogs.emoji_tracker')
        print("Successfully loaded EmojiTracker cog.")
    except commands.ExtensionAlreadyLoaded:
        # If the bot reconnects rapidly, the extension might already be loaded.
        pass 
    except Exception as e:
        # Catch any errors during loading
        print(f"Failed to load EmojiTracker cog: {e}")

bot.run(TOKEN)