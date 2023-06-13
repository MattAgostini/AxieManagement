import requests
import logging
import json
import hashlib
import string
import secrets
from discord.ext import commands
from backend.database.account_database import AccountEntry

import backend.transaction.utilities as utilities
import disbot.command_utils as CommandUtil
import disbot.battles as Battles
import backend.database.database_util as DbUtil
from backend.parse_accounts import parse_ronin_string


async def check_payout_address_set(ctx, account_entry: AccountEntry) -> bool:
    is_set = account_entry.account.payout_addr is not None
    if not is_set:
        await ctx.channel.send(
            "Please set your payout address before playing:\n"
            "type '!setPayoutAddress <your_payout_address>'"
        ) 
    return is_set


class ScholarCommands(commands.Cog):
    @commands.command(name='info', help='Displays scholar info')
    async def get_scholar_info(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        embed = await CommandUtil.get_account_info(account_entry)
        await ctx.channel.send(embed=embed)

    @commands.command(name='qr', help='Generates and sends a QR code')
    async def get_qr_code(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        if not await check_payout_address_set(ctx, account_entry): return
        await CommandUtil.get_qrcode(ctx)

    @commands.command(name='pass', help='Sends email and password information')
    async def get_password(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        if not await check_payout_address_set(ctx, account_entry): return
        await ctx.author.create_dm()
        await ctx.author.dm_channel.send(
            f"Hello {ctx.author.name}\n"
            "Here is your email and password to login:\n"
            f"Email: {account_entry.account.account_email}\n"
            f"Password: {account_entry.account.account_password}\n"
            "Remember to keep this information safe. Don't let anyone see it!")

    @commands.command(name='resetPass', help='Resets your password to a random 16 character string')
    async def reset_password(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return

        h = hashlib.new('sha256')
        h.update(account_entry.account.account_password.encode())
        hashed_old_password = h.hexdigest()

        new_password = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

        token = utilities.generate_access_token(account_entry.account)
        headers = {
            "User-Agent": utilities.USER_AGENT,
            "authorization": f"Bearer {token}"
        }
        payload = {
            "operationName": "UpdatePassword",
            "variables": {
                "password": new_password,
                "oldPassword": hashed_old_password
            },
            "query": "mutation UpdatePassword($password: String!, $oldPassword: String!) {"
            "   updatePassword(newPassword: $password, password: $oldPassword) {"
            "       result"
            "       __typename"
            "   }"
            "}"
        }
        try:
            url = "https://graphql-gateway.axieinfinity.com/graphql"
            response = requests.request("POST", url, headers=headers, json=payload)
            json_data = json.loads(response.text)
            logging.info(f"Request to reset password of scholar ({str(account_entry.account)}) : {json_data}")
            result = json_data['data']['updatePassword']['result']
            if not result: raise Exception("Result was unsuccessful")
        except Exception as e:
            await ctx.author.create_dm()
            await ctx.author.dm_channel.send(
                f"Hello {ctx.author.name}\n"
                "There was an issue resetting your password, please contact a manager")
            return

        account_entry.account.account_password = new_password
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)

        await ctx.author.create_dm()
        await ctx.author.dm_channel.send(
            f"Hello {ctx.author.name}\n"
            "Here is your email and new password to login:\n"
            f"Email: {account_entry.account.account_email}\n"
            f"Password: {account_entry.account.account_password}\n"
            "Remember to keep this information safe. Don't let anyone see it!\n"
            "Do NOT change password on marketplace, please use the bot if you want a different password")

    @commands.command(name='slp', help='Gets your SLP information')
    async def get_slp(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        embed = await CommandUtil.get_player_slp(account_entry)
        await ctx.channel.send(embed=embed)

    @commands.command(name='battles', help='Gets your recent and overall battle statistics')
    async def get_battles(self, ctx):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        await Battles.get_account_battles(ctx, account_entry)

    @commands.command(name='setPayoutAddress', help='Sets your payout address')
    async def set_payout_address(self, ctx, addr: str):
        if not CommandUtil.is_open_command_channel(str(ctx.channel)): return
        account_entry = DbUtil.account_db.get_account_from_discord_id(ctx.author.id)
        if account_entry is None:
            await ctx.channel.send("User not found in database") 
            return
        if parse_ronin_string(addr) is None:
            await ctx.channel.send("That payout address is invalid, please fix")
            return
        account_entry.account.payout_addr = addr
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        await ctx.channel.send("Your payout address was updated successfully")
