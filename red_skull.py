import os
import discord
from discord import Embed
from discord.ext import commands
from snap_data import Card, Location

TOKEN = os.getenv('DISCORD_TOKEN')
embed = Embed()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.command(name='skull')
async def on_message(message):
    quote = 'Leave Red Skull alone, please. I beg of you.'
    await message.send(quote)

@bot.command(name='cringe')
async def on_message(message):
    quote = 'day'
    await message.send(quote)

@bot.command(name='ban')
async def on_message(message, *, arg):
    await message.send('User {user} has been permanently banned from the server, what a loser! <:day:1072575755256598559>'.format(user=arg))

@bot.command(name='card')
async def get_card(message, *, arg):
    
    correct_case = " ".join([word.capitalize() for word in arg.split()])

    try:
        card = Card(correct_case)
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

        ### TODO ADD MarvelSnapZone page links
        embed.url = loc.webpage
        embed.add_field(name='Location', value=loc.loc_name, inline=False)
        embed.add_field(name='Effect', value=loc.effect, inline=False)

        ### TODO: ADD LOCATION IMAGE URLS TO JSON FILE
        embed.set_image(url=loc.image)
        embed.set_footer(text='Created by unlimited_powah')

        await message.send(embed = embed)
    except:
        await message.send('That location doesn\'t exist you jabroni.')

bot.run(TOKEN)