import logging
import os
import urllib
import discord
import requests
import pathlib
from PIL import Image
from datetime import datetime, timedelta


from disbot.blocking_functions import makeJsonRequest
from backend.database.account_database import AccountEntry

GAME_API = "https://game-api-pre.skymavis.com"
PROXY_API = "https://game-api.axie.technology"
CACHE_TIME = 30 # Minutes

battlesCache = {}

async def get_account_battles(context, account_entry: AccountEntry) -> None:
    global battlesCache

    IMAGE_DIRECTORY = pathlib.Path(__file__).parent.resolve() / 'images/'

    if not  os.path.isdir(IMAGE_DIRECTORY):
        os.makedirs(IMAGE_DIRECTORY)
    
    # Load from cache if we can
    if account_entry.public_addr in battlesCache and battlesCache[account_entry.public_addr]["cache"] > datetime.utcnow():
        logging.info("Game data was found in the cache")
        file = discord.File(battlesCache[account_entry.public_addr]["data"]["image"], filename="image.png")
        await context.channel.send(file=file, embed=battlesCache[account_entry.public_addr]["data"]["embed"])
        return

    headers = {
        'Content-Type': 'application/json',
    }
    ronin_addr = account_entry.public_addr.replace("ronin:", "0x")
    url = f"{PROXY_API}/logs/pvp/{ronin_addr}"
    jsonDatBattle = requests.request("GET", url, headers=headers)
    jsonDatBattle = jsonDatBattle.json()

    urlRank = f"{GAME_API}/leaderboard?client_id={ronin_addr}&offset=0&limit=0"
    jsonDatRank = makeJsonRequest(urlRank, "none")

    if jsonDatBattle is None or jsonDatRank is None:
        logging.error("Failure to get account game data")
        context.channel.send("There was an error retrieving your battle info")
        return

    cacheExp = datetime.utcnow() + timedelta(minutes=CACHE_TIME)
    try:
        battles = jsonDatBattle['battles']

        if battles is None:
            embed = discord.Embed(title="Account Recent Battles", description="Recent battles for address " + account_entry.public_addr,
                                  timestamp=datetime.utcnow(), color=discord.Color.blue())
            embed.add_field(name="Error", value=f"There are no recent battles for this account")
            await context.channel.send(embed=embed)
            return

        # Arena data, mmr/rank
        player = jsonDatRank['items'][1]
        name = player["name"]
        mmr = int(player["elo"])

        axieIds = []

        wins = 0
        losses = 0
        lastTime = None
        latestMatches = []
        for battle in battles:
            result = None

            if lastTime is None:
                lastTime = datetime.strptime(battle['game_started'], "%Y-%m-%dT%H:%M:%S") #TODO: Need utc time here?

            # opponent ronin
            opponent = None
            if battle['first_client_id'] == ronin_addr:
                opponent = battle['second_client_id']
                if len(axieIds) == 0:
                    axieIds = battle['first_team_fighters']
            else:
                opponent = battle['first_client_id']
                if len(axieIds) == 0:
                    axieIds = battle['second_team_fighters']

            # count draw
            if battle['winner'] is None:
                pass
            # count win
            elif battle['winner'] == ronin_addr:
                wins += 1
                result = 'win'
            # count loss
            else:
                losses += 1
                result = 'lose'

            # opponent ronin
            opponent = None
            if battle['first_client_id'] == ronin_addr:
                opponent = battle['second_client_id']
            else:
                opponent = battle['first_client_id']

            if len(latestMatches) < 5:
                latestMatches.append({'result': result,
                                      'replay': f'https://cdn.axieinfinity.com/game/deeplink.html?f=rpl&q={battle["battle_uuid"]}', 
                                      'opponent': opponent})

        
        axieImages = []
        combinedImg = None
        combinedIds = None
        imgErr = False
        for axieId in axieIds:
            imgPath = f'{IMAGE_DIRECTORY}{axieId}.png'
            if os.path.exists(imgPath):
                axieImages.append(imgPath)
            else:
                axieUrl = f'https://storage.googleapis.com/assets.axieinfinity.com/axies/{axieId}/axie/axie-full-transparent.png'
                res = saveUrlImage(axieUrl, imgPath)
                if res is None:
                    imgErr = True
                    break
                else:
                    axieImages.append(imgPath)

        if not imgErr:
            combinedIds = f'{IMAGE_DIRECTORY}/{axieIds[0]}-{axieIds[1]}-{axieIds[2]}.png'
            combinedImg = f'{IMAGE_DIRECTORY}/{axieIds[0]}-{axieIds[1]}-{axieIds[2]}.png'
            if not os.path.exists(combinedImg):
                res = concat_images(axieImages, combinedImg)
                if res is None:
                    imgErr = True
        

        matches = wins + losses
        winrate = 0
        loserate = 0
        if matches > 0:
            winrate = round(wins / matches * 100, 2)
            loserate = round(losses / matches * 100, 2)

        replayText = ""
        resultText = ""
        count = 1
        for match in latestMatches:
            resultText += match['result'] + '\n'
            replayText += '[Replay {}]({})\n'.format(count, match['replay'])
            count += 1

        embed = discord.Embed(title="Account Recent Battles", description="Recent battles for address " + account_entry.public_addr,
                              timestamp=datetime.utcnow(), color=discord.Color.blue())
        embed.add_field(name=":book: In Game Name", value=f"{name}")
        embed.add_field(name=":clock1: Last Match Time", value=f"{lastTime}")
        embed.add_field(name=":anger: Arena Matches", value=f"{matches}")
        embed.add_field(name=":crossed_swords: Arena MMR", value=f"{mmr}")
        embed.add_field(name=":dagger: Arena Wins", value=f"{wins}, {winrate}%")
        embed.add_field(name=":broken_heart: Arena Losses", value=f"{losses}, {loserate}%")
        embed.add_field(name="Last 5 Results", value=f"{resultText}")
        embed.add_field(name="Last 5 Replays", value=f"{replayText}")

        if not imgErr:
            file = discord.File(combinedIds, filename="image.png")
            embed.set_image(url=f"attachment://image.png")

        res = {
            'embed': embed,
            'name': name,
            'matches': matches,
            'wins': wins,
            'losses': losses,
            'winrate': winrate,
            'loserate': loserate,
            'latest': latestMatches,
            'replays': replayText
        }

        if not imgErr:
            res['image'] = combinedImg

        # save to the cache
        battlesCache[account_entry.public_addr] = {"data": res, "cache": cacheExp}
        await context.channel.send(file=file, embed=res['embed'])

    except Exception as e:
        logging.error(e)
        return

# fetch a remote image
def saveUrlImage(url, name):
    try:
        urllib.request.urlretrieve(url, name)
        return name
    except Exception as e:
        logging.error(f"Erroring downloading image {url}: {e}")
        return None


def concat_images(imagePaths, name, excessPxl=0):
    try:
        images = [Image.open(x) for x in imagePaths]
        widths, heights = zip(*(i.size for i in images))

        total_width = sum(widths) + excessPxl
        max_height = max(heights)

        new_im = Image.new('RGBA', (total_width, max_height), (0, 0, 0, 0))

        x_offset = excessPxl
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]

        new_im.save(name)
        return name
    except Exception as e:
        logging.error(f"Error combining images: {e}")
        return None
