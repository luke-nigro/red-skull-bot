import os
import random
import discord
import asyncio
from discord import Embed
from discord.ext import commands

TOKEN = os.getenv('DISCORD_TOKEN')
embed = Embed()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.command(name='skull')
async def on_message(message):
    await message.send('Leave Red Skull alone, please. I beg of you.')

@bot.command(name='cringe')
async def on_message(message):  # noqa: F811
    await message.send('day')

@bot.command(name='bonk')
async def on_message(message):
    await message.send('https://media2.giphy.com/avatars/DogeBONK/coZ41g2NwRFS.gif')

@bot.command(name='ban')
async def on_message(message, *, arg):
    await message.send(f'User {arg} has been permanently banned from the server, what a loser! <:day:1072575755256598559>')

@bot.command(name='boc')
async def on_message(message):
    await message.send("Claude told me you are wrong and that I am very smart. Trump is right about everything. My homeschooled kids will be totally normal.")

@bot.command(name='roll')
async def on_message(message, *, arg):
    if not arg.isdigit():
        await message.send("That's not a number you moron, pick a different number")
    elif int(arg) < 1:
        await message.send("Pick a number greater than 1 you moron")
    else:
        roll = random.randint(1, int(arg))
        await message.send(f"You rolled a {roll}.")

@bot.command(name='squash')
async def on_message(message):
    await message.send("Yeah man I'm going to need you to go ahead and calm down for me. Can you do that?")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if 'cringe' in message.content.lower():
        roll = random.randint(1, 100)
        if roll == 1:
            await message.reply("you're cringe bro")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if 'cheney' in message.content.lower():
        await message.reply("Shut up you idiot that’s not why the Dems lost the election.")

bot.run(TOKEN)