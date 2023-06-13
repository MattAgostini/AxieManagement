import logging
import discord
import sys
from discord.ext import commands
from datetime import datetime
from pathlib import Path

import backend.encryption.encryption_util as EncryptUtil
import disbot.command_utils as CommandUtil
import backend.parse_env as EnvVar
from disbot.scholar_commands import ScholarCommands
from disbot.manager_commands import ManagerCommands
from disbot.owner_commands import OwnerCommands


# Set up logging
path = Path("log/")
path.mkdir(parents=True, exist_ok=True)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.root.handlers = []
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler(path / "discord-{:%Y-%m-%d}.log".format(datetime.now())),
        logging.StreamHandler(sys.stdout)
    ]
)


intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    assert len(bot.guilds) == 1, "Bot cannot be connected to more than one server"
    guild = bot.guilds[0]
    logging.info(f'{bot.user} is connected to the following guild: {guild.name}')
    CommandUtil.set_slp_emoji_id(guild)


def run():
    logging.info("Running Discord bot!")
    EncryptUtil.login()
    bot.add_cog(ScholarCommands())
    bot.add_cog(ManagerCommands(bot))
    bot.add_cog(OwnerCommands(bot))
    bot.run(EnvVar.DISCORD_TOKEN)
