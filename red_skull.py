import os
import random
import discord
import asyncio
from discord import Embed
from discord.ext import commands
from snap_data import Card, Location

TOKEN = os.getenv('DISCORD_TOKEN')
embed = Embed()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.command(name='skull')
async def on_message(message):
    await message.send('Leave Red Skull alone, please. I beg of you.')

@bot.command(name='cringe')
async def on_message(message):
    await message.send('day')

@bot.command(name='bonk')
async def on_message(message):
    await message.send('https://media2.giphy.com/avatars/DogeBONK/coZ41g2NwRFS.gif')

@bot.command(name='ban')
async def on_message(message, *, arg):
    await message.send('User {user} has been permanently banned from the server, what a loser! <:day:1072575755256598559>'.format(user=arg))

@bot.command(name='roll')
async def on_message(message, *, arg):
    try:
        roll = random.randint(1,int(arg))
        await message.send("A `d{d}` was rolled and you got `{num}`.".format(d=arg, num=roll))
    except:
        await message.send("That's not a number you moron, pick a different number")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if 'cringe' in message.content.lower():
        roll = random.randint(1, 10)
        if roll == 1:
            # Prevent the member from sending messages in all text channels on the server for 1 minute
            overwrite = discord.PermissionOverwrite()
            overwrite.send_messages = False
            await asyncio.gather(*[channel.set_permissions(message.author, overwrite=overwrite, reason="Timed out for using a banned word") for channel in message.guild.text_channels])
            await message.reply('{auth} has been timed out for being cringy, what an idiot!'.format(auth=message.author))
            await asyncio.sleep(60)  # Wait for 1 minute
            await asyncio.gather(*[channel.set_permissions(message.author, overwrite=None, reason="Timeout expired") for channel in message.guild.text_channels])
        else:
            await message.reply('got away with it this time')

@bot.command(name='card')
async def get_card(message, *, arg):

    try:
        card = Card(arg)
        embed.clear_fields()
        embed.title = card.card_name
        embed.color = discord.Color.blue()
        embed.url = card.webpage
        embed.add_field(name='Ability', value=card.ability, inline=False)
        embed.add_field(name='Cost', value=card.cost, inline=True)
        embed.add_field(name='Power', value=card.power, inline=True)
        embed.set_image(url=card.image)
        embed.set_footer(text='Created by unlimited_powah')

        await message.send(embed = embed)
    except:
        await message.send('That card doesn\'t exist you nimrod.')

@bot.command(name='location')
async def get_card(message, *, arg):
    
    correct_case = " ".join([word.capitalize() for word in arg.split()])

    try:
        loc = Location(correct_case)
        embed.clear_fields()
        embed.title = loc.loc_name
        embed.color = discord.Color.blue()

        embed.url = loc.webpage
        embed.add_field(name='Location', value=loc.loc_name, inline=False)
        embed.add_field(name='Effect', value=loc.effect, inline=False)

        embed.set_image(url=loc.image)
        embed.set_footer(text='Created by unlimited_powah')

        await message.send(embed = embed)
    except:
        await message.send('That location doesn\'t exist you jabroni.')

bot.run(TOKEN)