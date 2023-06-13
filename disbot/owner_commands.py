import logging
import discord
from discord.ext import commands

import backend.transaction.utilities as utilities
import disbot.command_utils as CommandUtil
import backend.database.database_util as DbUtil
import backend.parse_env as EnvVar
from backend.parse_accounts import AccountType
from backend.transaction.payments import DEVELOPER_FEE
from disbot.blocking_functions import claim_all, payout_all, reclaim_axies


async def isOwner(context, discord_id: int):
    account_entry = DbUtil.account_db.get_account_from_discord_id(discord_id)
    if account_entry is None:
        await context.channel.send("User not found in database")
        return False
    if AccountType.Owner in account_entry.account.account_types: return True
    else:
        await context.channel.send("You must be an owner to use this command")
        return False


class OwnerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='getManagers', help='Displays all the configured managers in the database')
    async def get_managers(self, ctx):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        manager_entries = DbUtil.account_db.get_manager_entries()
        logging.info("Getting manager entries!")
        if len(manager_entries) == 0:
            await ctx.channel.send("No managers found")
            return
        response = '\n'.join([f'{manager.account}:\t{await self.bot.fetch_user(manager.discord_id)}' for manager in manager_entries])
        await ctx.send(response)

    @commands.command(name='addManager', help='Gives an existing scholar the manager role')
    async def add_manager(self, ctx, discord_user: discord.User):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database")
            return
        account_entry.account.account_types.append(AccountType.Manager)
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        await ctx.channel.send("Manager added successfully")

    @commands.command(name='removeManager', help='Removes the manager role from an existing scholar')
    async def remove_manager(self, ctx, discord_user: discord.User):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database")
            return
        if AccountType.Manager not in account_entry.account.account_types:
            await ctx.channel.send("User is not a manger")
            return
        account_entry.account.account_types.remove(AccountType.Manager)
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        await ctx.channel.send("Manager removed successfully")

    @commands.command(name='setPayoutPercentage', help=f"Sets a scholar's payout percentage (0-{100 - DEVELOPER_FEE})")
    async def set_payout_percentage(self, ctx, discord_user: discord.User, percentage: int):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(discord_user.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database")
            return
        if percentage not in range(101 - DEVELOPER_FEE):
            await ctx.channel.send("Invalid percentage")
            return
        account_entry.account.payout_percentage = percentage
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        await ctx.channel.send("Scholar payout percentage updated")

    @commands.command(name='updateAllScholarNames', help="Updates all scholar names in the marketplace to match the database")
    async def update_all_scholar_names(self, ctx):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        await ctx.channel.send("Updating scholar names, this may take a few minutes")
        scholar_entries = DbUtil.account_db.get_scholar_entries()

        for scholar in scholar_entries:
            marketplace_account_name = str(scholar.account)
            token = utilities.generate_access_token(scholar.account)
            await CommandUtil.update_marketplace_account_name(marketplace_account_name, token)

        await ctx.channel.send("Scholar names updated")

    @commands.command(name='setAccountPassword', help="Sets a given account's password (after you've changed it through the website)")
    async def set_account_password(self, ctx, seed_id: int, seed_account_num: int, new_password : str):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        
        account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
        account_entry.account.account_password = new_password
        account_entry = DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        await ctx.channel.send("Account password updated successfully")

    @commands.command(name='claimAll', help="Claims SLP from all accounts (unstable and temporary)")
    async def claim_all_accounts(self, ctx):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        if not EnvVar.BOT_WEB3_ENABLED:
            await ctx.channel.send("Web3 transactions from discord are disabled")
            return 
        
        await claim_all()
        await ctx.channel.send("Claiming complete. Please check the logs for failures")


    @commands.command(name='payoutAll', help="Pays out all SLP from non-vault accounts (unstable and temporary)")
    async def payout_all_accounts(self, ctx):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        if not EnvVar.BOT_WEB3_ENABLED:
            await ctx.channel.send("Web3 transactions from discord are disabled")
            return 
        
        await payout_all()
        await ctx.channel.send("Payout complete. Please check the logs for failures")


    @commands.command(name='reclaimAxies', help="Sends all the axies on an account to the seed vault (unstable and temporary)")
    async def reclaim_axies_from_account(self, ctx, seed_id: int, seed_account_num: int):
        if not CommandUtil.is_admin_command_channel(str(ctx.channel)): return
        if not await isOwner(ctx, ctx.author.id): return
        if not EnvVar.BOT_WEB3_ENABLED:
            await ctx.channel.send("Web3 transactions from discord are disabled")
            return

        account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
        if account_entry is None:
            await ctx.channel.send("That account ID was out of range")
            return
        if AccountType.Vault in account_entry.account.account_types:
            await ctx.channel.send("A vault is an invalid target for this command")
            return

        await reclaim_axies(seed_id, seed_account_num)
        await ctx.channel.send("Axie reclaimation complete. Please check the logs for failures")
