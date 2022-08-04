from os import environ
# from discord.ext.commands import Bot
from discord.ext import commands
# from commands.commands import MainCommands

bot = commands.Bot(command_prefix='/', description='A bot for the Discord server')

@commands.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to a Discord!')

bot.add_command(ping)

bot.run(environ.get('BOT_TOKEN'))
