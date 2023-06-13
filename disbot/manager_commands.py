import os
import discord
import pandas as pd
from discord.ext import commands
from discord.ext import tasks
import time
from datetime import datetime, timezone
from backend.database.account_database import AccountEntry

import backend.transaction.utilities as utilities
import disbot.command_utils as CommandUtil
import backend.database.database_util as DbUtil
import backend.parse_env as EnvVar
from disbot.blocking_functions import build_accounts_spreadsheet, build_daily_report_spreadsheet
from backend.parse_accounts import DEFAULT_ACCOUNT_NAME, AccountType


async def is_manager(context, discord_id: int):
    account_entry = DbUtil.account_db.get_account_from_discord_id(discord_id)
    if account_entry is None:
        await context.channel.send("User not found in database")
        return False
    if AccountType.Manager in account_entry.account.account_types: return True
    if AccountType.Owner in account_entry.account.account_types: return True
    else:
        await context.channel.send("You must be a manager to use this command") 
        return False


async def clear_account(ctx, account_entry: AccountEntry):
    if AccountType.Owner in account_entry.account.account_types:
        await ctx.channel.send("You cannot remove the owner")
        return
    if AccountType.Manager in account_entry.account.account_types:
        await ctx.channel.send("You cannot remove other managers")
        return
    account_entry.account_name = DEFAULT_ACCOUNT_NAME
    account_entry.discord_id = None
    account_entry.account.account_name = DEFAULT_ACCOUNT_NAME
    account_entry.account.account_types = []
    account_entry.account.discord_id = None
    if EnvVar.CLEAR_PAYOUT_ADDR_ON_REMOVAL:
        account_entry.account.payout_addr = None
    DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
    await ctx.channel.send("Scholar successfully removed")


class ManagerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.get_and_display_daily_report.start()

    @commands.command(name='getScholar', help='Displays scholar info of given scholar')
    async def get_scholar(self, ctx, discord_user: discord.User):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        embed = await CommandUtil.get_account_info(account_entry)
        await ctx.channel.send(embed=embed)

    @commands.command(name='addScholar', help='Adds scholar to an account')
    async def add_scholar(self, ctx, discord_user: discord.User, seed_id, seed_account_num):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is not None:
            await ctx.channel.send("That scholar already has an account")
            return

        account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
        if account_entry is None:
            await ctx.channel.send("That account ID was out of range")
            return
        if account_entry.discord_id is not None:
            await ctx.channel.send("That account ID already has a scholar, please select another one")
            return
        if AccountType.Vault in account_entry.account.account_types:
            await ctx.channel.send("That account ID is a Vault, please select another one")
            return
        account_entry.account_name = discord_user.name
        account_entry.discord_id = discord_user.id
        account_entry.account.account_name = discord_user.name
        account_entry.account.account_types = [AccountType.Scholar]
        account_entry.account.discord_id = discord_user.id
        account_entry.account.payout_addr = None
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)

        marketplace_account_name = str(account_entry.account)
        token = utilities.generate_access_token(account_entry.account)
        await CommandUtil.update_marketplace_account_name(marketplace_account_name, token)

        await ctx.channel.send("Scholar successfully added")
        guild = self.bot.guilds[0]
        open_channel = discord.utils.get(guild.text_channels, name=EnvVar.OPEN_BOT_CHANNEL)
        await open_channel.send(
            f'{discord_user.mention}, you have been added as a scholar! Please type "!setPayoutAddress <your_payout_address>" '
            'to get started. Then type !qr or !pass to receive your login info. '
            'If you have any questions, please ask your team leader or other scholars for assistance!'
        )

    @commands.command(name='removeScholar', help='Removes scholar from their account')
    async def remove_scholar(self, ctx, discord_user: discord.User):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is None:
            await ctx.channel.send("That user is not a scholar")
            return
        await clear_account(ctx, account_entry)

    @commands.command(name='clearAccount', help='Removes scholar from given account if present')
    async def clear_account(self, ctx, seed_id: int, seed_account_num: int):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
        if account_entry is None:
            await ctx.channel.send("That account ID was out of range")
            return
        if account_entry.discord_id is None:
            await ctx.channel.send("That account ID does not have a scholar")
            return
        await clear_account(ctx, account_entry)

    @commands.command(name='getAccounts', help='Displays information of all accounts')
    async def get_accounts(self, ctx):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        fName = await build_accounts_spreadsheet(self.bot)
        await ctx.channel.send(file=discord.File(fName))
        os.remove(fName)

    @commands.command(name='getAccount', help='Displays information of given account')
    async def get_account(self, ctx, seed_id: int, seed_account_num: int):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await is_manager(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
        if account_entry is None:
            await ctx.channel.send("That account ID was out of range")
            return
        embed = await CommandUtil.get_account_info(account_entry)
        await ctx.channel.send(embed=embed)

    @tasks.loop(seconds=60.0)
    async def get_and_display_daily_report(self):
        await self.bot.wait_until_ready()
        time = datetime.now(timezone.utc)
        if time.hour == 0 and time.minute == 0:
            await CommandUtil.get_daily_tracker_data()
            guild = self.bot.guilds[0]
            for channel in guild.channels:
                if channel.name == EnvVar.ADMIN_ALERT_CHANNEL:
                    wanted_channel_id = channel.id
            admin_channel = self.bot.get_channel(wanted_channel_id)
            await CommandUtil.display_daily_report(self.bot, admin_channel)

            fName = await build_daily_report_spreadsheet()
            await admin_channel.send(file=discord.File(fName))
            os.remove(fName)

            for channel in guild.channels:
                if channel.name == EnvVar.OPEN_ALERT_CHANNEL:
                    wanted_channel_id = channel.id
            open_channel = self.bot.get_channel(wanted_channel_id)
            await CommandUtil.send_daily_leaderboard(self.bot, open_channel)
