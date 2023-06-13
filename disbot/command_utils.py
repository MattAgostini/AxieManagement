import logging
import os
import qrcode
import json
import discord
import requests
import pathlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import backend.transaction.utilities as utilities
import backend.database.database_util as DbUtil
import backend.parse_env as EnvVar
from disbot.blocking_functions import update_databases_with_tracker
from backend.database.account_database import AccountEntry
from backend.database.slp_tracking_database import TrackingEntry
from backend.parse_accounts import DEFAULT_ACCOUNT_NAME
from backend.transaction.claims import get_slp_data
from backend.query_coin_base import PHP, SLP, USD, query_coin_base, get_exchange_rate

CACHE_TIME = 30 # Minutes
GRAPHQL = "https://graphql-gateway.axieinfinity.com/graphql"
GAME_API = "https://game-api-pre.skymavis.com"
PROXY_API = "https://game-api.axie.technology"

def is_open_command_channel(channel: str) -> bool:
    return (channel in [EnvVar.OPEN_BOT_CHANNEL, EnvVar.ADMIN_BOT_CHANNEL])

def is_admin_command_channel(channel: str) -> bool:
    return (channel in [EnvVar.ADMIN_BOT_CHANNEL])

slpEmojiId = ""
def set_slp_emoji_id(guild):
    global slpEmojiId
    for emoji in guild.emojis:
        if emoji.name == "slp":
            slpEmojiId = emoji.id


async def get_account_info(account_entry: AccountEntry):
    embed = discord.Embed(title="Scholar Information", color=discord.Color.blue())

    embed.add_field(name="Seed ID", value=f"{account_entry.seed_id}")
    embed.add_field(name="Account Number", value=f"{account_entry.seed_account_num}")
    embed.add_field(name="Scholar Name", value=f"{account_entry.account_name}")
    embed.add_field(name="Discord ID", value=f"{account_entry.discord_id}")

    if len(account_entry.account.account_types) == 0: role_str = "None"
    else: role_str = '\n'.join([account_type.value for account_type in account_entry.account.account_types])
    embed.add_field(name="Roles", value=f"{role_str}")

    embed.add_field(name="Payout Percentage", value=f"{account_entry.account.payout_percentage}%")
    embed.add_field(name="Number of Axies", value=f"{account_entry.num_axies}")

    embed.add_field(name="Account Address", value=f"{account_entry.public_addr}")
    embed.add_field(name="Payout Address", value=f"{account_entry.account.payout_addr}")
    return embed


async def get_qrcode(context):
    QR_DIRECTORY = pathlib.Path(__file__).parent.resolve() / 'qr/'

    if not os.path.isdir(QR_DIRECTORY):
        os.makedirs(QR_DIRECTORY)

    if os.path.exists(f"{QR_DIRECTORY}/{str(context.author.id)}QRCode.png"):
        os.remove(f"{QR_DIRECTORY}/{str(context.author.id)}QRCode.png")

    account_entry = DbUtil.account_db.get_account_from_discord_id(context.author.id)
    if account_entry is not None:
        accessToken = utilities.generate_access_token(account_entry.account)
        if accessToken is None:
            msg = 'Sorry <@' + str(context.author.id) + '>, there was an issue with your request. Please try again later.'
            await context.channel.send(msg)
            return

        def getQRCode(accessToken, discordID):
            img = qrcode.make(accessToken)
            imgName = f"{QR_DIRECTORY}/{str(discordID)}QRCode.png"
            img.save(imgName)
            return imgName

        qrFileName = getQRCode(accessToken, context.author.id)

        await context.author.create_dm()
        await context.author.dm_channel.send(
            f"Hello {context.author.name}\nHere is your new QR Code to login:\n"
            "Remember to keep your QR code safe and don't let anyone else see it!", 
            file=discord.File(qrFileName))
        logging.info("This user received their QR Code : " + context.author.name)
    else:
        logging.warning(f"This user didn't receive a QR Code : {context.author.name}")
        msg = 'Hello <@' + str(context.author.id) + '>. Unfortunately, you do not appear to be a scholar.'
        await context.channel.send(msg)
    return


async def display_daily_report(bot, channel):
    guild = bot.guilds[0]

    entries = [
        entry for entry in DbUtil.account_db.get_scholar_entries() 
        if entry.account.account_name != DEFAULT_ACCOUNT_NAME and entry.num_axies != 0
    ]

    tracker_entries = [DbUtil.slp_tracking_db.get_slp_tracking_entry_from_seed_and_number(entry.seed_id, entry.seed_account_num) for entry in entries]

    previous_day = []
    for i in range(len(tracker_entries)):
        previous_day.append({
            "account": entries[i].account,
            "slp_earned": tracker_entries[i].daily_slp[-1],
            'days_missed': _check_how_many_days_missed(tracker_entries[i])
        })
    previous_day = sorted(previous_day, key=lambda item: item['slp_earned'], reverse=True)

    daily_slp_earned = 0
    for scholar in previous_day:
        daily_slp_earned += scholar['slp_earned']
    daily_slp_earned_avg = 0
    if len(previous_day) > 0: daily_slp_earned_avg = round(daily_slp_earned / len(previous_day))

    missed_three_or_more_days = [scholar['account'] for scholar in previous_day if scholar['days_missed'] > 3]

    slp_icon = '<:slp:{}>'.format(slpEmojiId)

    embed = discord.Embed(title="Daily Stats", description=f"Daily stats for {guild.name} scholarship", color=discord.Color.blue())
    embed.add_field(name="SLP earned today", value=f"{round(daily_slp_earned)} {slp_icon}")
    embed.add_field(name="SLP due to Vault", value=f"{round(daily_slp_earned * 0.55)} {slp_icon}")
    embed.add_field(name="SLP due to Dev", value=f"{round(daily_slp_earned * 0.05)} {slp_icon}")
    embed.add_field(name="Scholar Avg SLP", value=f"{daily_slp_earned_avg} {slp_icon}")
    await channel.send(embed=embed)

    scholar_warn = "The following scholars have missed 3 or more days in a row and should receive a warning if they haven't already.\n"
    for account in missed_three_or_more_days:
        discord_user = None
        if account.discord_id is not None: discord_user = await bot.fetch_user(account.discord_id)
        scholar_warn += f"\t{account}\t{discord_user.mention}\n"
    await channel.send(scholar_warn)

def _check_how_many_days_missed(slp_tracking_entry: TrackingEntry) -> int:
    days_missed = 0
    for daily_slp in reversed(slp_tracking_entry.daily_slp):
        if daily_slp > 0: break
        days_missed += 1
    return days_missed


async def send_daily_leaderboard(bot, channel):
    leaderboard_size = 25

    trackable_entries = [
        entry for entry in DbUtil.account_db.get_scholar_entries() 
        if entry.account.account_name != DEFAULT_ACCOUNT_NAME and entry.num_axies != 0
    ]

    sorted_trackable_entries = sorted(trackable_entries, key=lambda item: item.scholar_page_data.unclaimed_slp, reverse=True)
    if len(sorted_trackable_entries) < leaderboard_size: leaderboard_size = len(sorted_trackable_entries)

    slp_icon = '<:slp:{}>'.format(slpEmojiId)
    embed = discord.Embed(title="SLP Leaderboard", description=f"Stats for top {leaderboard_size} earners", color=discord.Color.blue())
    for i in range(leaderboard_size):
        medal_icon = ""
        if i == 0: medal_icon = ":first_place:"
        elif i == 1: medal_icon = ":second_place:"
        elif i == 2: medal_icon = ":third_place:"

        account = sorted_trackable_entries[i]
        embed.add_field(
            name=f"{i+1}. {account.account_name}{medal_icon} - {account.mmr} MMR",
            value=f"Has earned a total of {account.scholar_page_data.unclaimed_slp} {slp_icon} this claim cycle!", inline=False
        )

    await channel.send(embed=embed)


async def send_daily_report_detailed(bot, channel):
    entries = [entry for entry in DbUtil.account_db.get_scholar_entries() if entry.account.account_name != DEFAULT_ACCOUNT_NAME]

    data = []
    for entry in entries:
        slp_tracking_entry = DbUtil.slp_tracking_db.get_slp_tracking_entry_from_seed_and_number(entry.seed_id, entry.seed_account_num)
        weekly_avg = round(sum(slp_tracking_entry.daily_slp[-7:]) / len(slp_tracking_entry.daily_slp[-7:]))
        data.append([entry.seed_id, entry.seed_account_num, entry.account_name, entry.mmr, weekly_avg, *(np.flip(slp_tracking_entry.daily_slp))])

    date_format_string = "%Y-%m-%d"
    current_date = datetime.now()
    dates = []
    for i in range(len(slp_tracking_entry.daily_slp)):
        dates.append(datetime.strftime(current_date + timedelta(days=-i), date_format_string))
    current_date = datetime.now()
    table = pd.DataFrame(data, columns=['seed_id', 'seed_account_num', 'name', 'mmr', "7 Day Avg", *dates])

    fName = os.getcwd() + f'/summary_detailed_{datetime.strftime(datetime.now(), date_format_string)}.xlsx'
    writer = pd.ExcelWriter(fName, engine='xlsxwriter')
    table.to_excel(writer, sheet_name='Sheet1', index=False)

    workbook = writer.book
    red_format = workbook.add_format({'bg_color': '#FFC7CE',
                                   'font_color': '#9C0006'})
    green_format = workbook.add_format({'bg_color': '#C6EFCE',
                                   'font_color': '#006100'})

    worksheet = writer.sheets['Sheet1']
    worksheet.set_column('C:C', 20)
    worksheet.set_column('D:BM', 15)
    worksheet.conditional_format(f'E2:BM{len(table) + 1}', 
                                {'type': 'cell',
                                 'criteria': '>=',
                                 'value': 150,
                                 'format': green_format})
    worksheet.conditional_format(f'E2:BM{len(table) + 1}', 
                                {'type': 'cell',
                                 'criteria': '<',
                                 'value': 150,
                                 'format': red_format})

    writer.close()
    await channel.send(file=discord.File(fName))
    os.remove(fName)


async def get_player_slp(account_entry: AccountEntry):
    slp_info_dict = get_slp_data(account_entry.account)
    slp_icon = '<:slp:{}>'.format(slpEmojiId)

    tracking_entry = DbUtil.slp_tracking_db.get_slp_tracking_entry_from_seed_and_number(account_entry.seed_id, account_entry.seed_account_num)

    current_slp = slp_info_dict['rawTotal']
    today_slp = int(current_slp - tracking_entry.total_slp[-1])
    yesterday_slp = int(tracking_entry.daily_slp[-1])
    before_yesterday_slp = int(tracking_entry.daily_slp[-2])

    embed = discord.Embed(title=f"{account_entry.account_name}'s SLP Count", color=discord.Color.blue())
    embed.add_field(name="Today", value=f"{today_slp} {slp_icon}")
    embed.add_field(name="Yesterday", value=f"{yesterday_slp} {slp_icon}")
    embed.add_field(name="Before Yesterday", value=f"{before_yesterday_slp} {slp_icon}")
    embed.add_field(name="Total Gained", value=f"{current_slp} {slp_icon}")

    last_claimed_date = datetime.fromtimestamp(slp_info_dict['lastClaimedItemAt'])
    next_claim_date = last_claimed_date + timedelta(days=14)
    date_format_string = "%Y-%m-%d"
    last_claimed_date_formatted = datetime.strftime(last_claimed_date, date_format_string)
    next_claim_date_formatted = datetime.strftime(next_claim_date, date_format_string)

    embed.add_field(name="Last Claim", value=f"{last_claimed_date_formatted}")
    embed.add_field(name="Next Claim", value=f"{next_claim_date_formatted}")

    unclaimed_slp = slp_info_dict['rawTotal'] - slp_info_dict['rawClaimableTotal']
    days_since_last_claim = (datetime.now() - last_claimed_date).days
    average_slp_day = 0
    if days_since_last_claim != 0:
        average_slp_day = round(unclaimed_slp / days_since_last_claim, 1)

    embed.add_field(name="Since Last Claim", value=f"{unclaimed_slp} {slp_icon}")
    embed.add_field(name="Daily Average", value=f"{average_slp_day} {slp_icon}")
    embed.add_field(name="Earning Percentage", value=f"{account_entry.account.payout_percentage}%")

    earning_slp = round(unclaimed_slp * (account_entry.account.payout_percentage / 100.0))
    usd_coinbase_df = query_coin_base(USD)
    php_coinbase_df = query_coin_base(PHP)

    embed.add_field(name="Earning SLP", value=f"{earning_slp} {slp_icon}")
    embed.add_field(name="Earning USD", value=f"~{round(earning_slp * get_exchange_rate(usd_coinbase_df, SLP), 2)}")
    embed.add_field(name="Earning PHP", value=f"~{round(earning_slp * get_exchange_rate(php_coinbase_df, SLP), 2)}")

    embed.set_footer(text="USD and PHP earnings are subject to change and estimated using coinbase.com")
    return embed


async def get_daily_tracker_data():
    logging.info("Getting scholar data for today")
    await update_databases_with_tracker()


async def update_marketplace_account_name(name: str, token):
    headers = {
        "User-Agent": utilities.USER_AGENT,
        "authorization": f"Bearer {token}"
    }
    payload = {
        "operationName": "UpdateProfileName",
        "variables": {
            "name": name
        },
        "query": "mutation UpdateProfileName($name: String!) {"
        "   updateProfileName(name: $name) {"
        "       __typename"
        "   }"
        "}"
    }
    url = "https://graphql-gateway.axieinfinity.com/graphql"
    try:
        response = requests.request("POST", url, headers=headers, json=payload)
        json_data = json.loads(response.text)
        return json_data
    except Exception as e:
        logging.critical(f"Error updating account name: {e}")
