import os
import discord
from discord import Embed
from discord.ext import commands
from dotenv import load_dotenv
from get_cards import Card

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
embed = Embed(title='Card Viewer')

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.command(name='skull')
async def on_message(message):
    quote = 'Red Skull will fuck your day up.'
    await message.send(quote)

@bot.command(name='card')
async def get_card(message, *, arg):
    
    correct_case = " ".join([word.capitalize() for word in arg.split()])

    try:
        card = Card(correct_case)
        embed.clear_fields()
        embed.title = card.card_name
        embed.add_field(name='Ability', value=card.ability, inline=False)
        embed.add_field(name='Cost', value=card.cost, inline=True)
        embed.add_field(name='Power', value=card.power, inline=True)
        embed.set_image(url=card.image)
        embed.set_footer(text='Created by unlimited_powah')

        await message.send(embed = embed)
    except:
        await message.send('That card doesn\'t exist you nimrod.')

bot.run(TOKEN)