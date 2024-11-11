"""
Created by Deltaion Lee (MCMi460) on Github
Based from NintendoClients' `examples/3ds/friends.py`
"""

# standard library
import argparse
import datetime
import io
import sys
import time
import traceback
import logging

# third-party libraries
import anyio
from nintendo import nasc
from nintendo.nex import backend, friends, settings
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session

sys.path.append('../')

# local libraries
from database import DiscordFriends, Friend, get_db_url, start_db_time
import api.love2 as love2
from api.networks import InvalidNetworkError, NetworkType
# pylint: disable=import-error, no-name-in-module
from api.private import (DEVICE_CERT, DEVICE_NAME, LANGUAGE, MAC_ADDRESS,
                         NINTENDO_NEX_PASSWORD, NINTENDO_PID, PID_HMAC,
                         PRETENDO_NEX_PASSWORD, PRETENDO_PID, REGION,
                         SERIAL_NUMBER)

logging.basicConfig(level=logging.INFO)

DELAY = 2
QUICKER = 15
BEGUN = time.time()
SCRAPE_ONLY = False

network: NetworkType = NetworkType.NINTENDO


async def main():
    engine = create_engine(get_db_url())
    session = Session(engine)

    while True:
        time.sleep(1)
        print('Grabbing new friends...')

        queried_friends = session.scalars(select(Friend).where(Friend.network == network)).all()
        if not queried_friends:
            continue

        all_friends = [(love2.friend_code_to_principal_id(f.friend_code), f.last_accessed) for f in queried_friends]
        friend_codes = [ f[0] for f in all_friends ]

        for i in range(0, len(friend_codes), 100):
            rotation = friend_codes[i:i+100]

            try:
                client = nasc.NASCClient()

                # TODO: This should be separate between networks.
                # E.g. if the friend code was is banned on one network,
                # you'd still be able to keep the friend code for the other network.
                client.set_title(0x0004013000003202, 20)
                client.set_locale(REGION, LANGUAGE)

                # storing the PID and NEX_PASSWORD in a dictonary would avoid that
                # api private would need to be eddited for that
                if network == NetworkType.NINTENDO:
                    client.set_url("nasc.nintendowifi.net")
                    PID = NINTENDO_PID
                    NEX_PASSWORD = NINTENDO_NEX_PASSWORD
                elif network == NetworkType.PRETENDO:
                    client.set_url("nasc.pretendo.cc")
                    client.context.set_authority(None)
                    PID = PRETENDO_PID
                    NEX_PASSWORD = PRETENDO_NEX_PASSWORD
                else:
                    raise InvalidNetworkError(
                        f"Network type {network} is not configured for querying"
                        )

                client.set_device(SERIAL_NUMBER, MAC_ADDRESS, DEVICE_CERT, DEVICE_NAME)
                client.set_user(PID, PID_HMAC)

                response = await client.login(0x3200)

                s = settings.load('friends')
                s.configure("ridfebb9", 20000)

                async with backend.connect(s, response.host, response.port) as be:
                    async with be.login(str(PID), NEX_PASSWORD) as client:
                        friends_client = friends.FriendsClientV1(client)
                        if time.time() - BEGUN < 30:
                            time.sleep(DELAY)
                            await friends_client.update_comment('3dsrpc.com')
                        since = time.time()

                        if time.time() - since > 3600:
                            break

                        time.sleep(DELAY)
                        print('Cleaning out to zero')
                        removables = await friends_client.get_all_friends()
                        for friend in removables:
                            time.sleep(DELAY / QUICKER)
                            await friends_client.remove_friend_by_principal_id(friend.pid)
                        print(f'Removed {str(len(removables))} friends')

                        removal_list = []
                        clean_up = []

                        # The add_friend_by_principal_ids method is not yet
                        # implemented on Pretendo, so this is a fix for now.
                        if network == NetworkType.PRETENDO:
                            for friend_pid in rotation:
                                time.sleep(DELAY / QUICKER)
                                await friends_client.add_friend_by_principal_id(0, friend_pid)
                        else:
                            time.sleep(DELAY)
                            await friends_client.add_friend_by_principal_ids(0, rotation)

                        time.sleep(DELAY)

                        # Determine which remote friends failed to add, and thus have unfriended us.
                        network_friends = await friends_client.get_all_friends()
                        if len(network_friends) < len(rotation):
                            for current_pid in rotation:
                                if current_pid not in [ f.pid for f in network_friends ]:
                                    removal_list.append(current_pid)

                        # Keep track of which current friends are within our current rotation.
                        # We'll remove them once game presences are updated.
                        x = network_friends
                        network_friends = []
                        for t1 in x:
                            if t1.pid in rotation:
                                network_friends.append(t1)
                            else:
                                clean_up.append(t1.pid)

                        for removed_friend in removal_list:
                            removed_friend_code = str(
                                love2.principal_id_to_friend_code(removed_friend)
                                ).zfill(12)

                            # Remove this friend code from both our tracked network friends and Discord friend codes.
                            session.execute(delete(Friend).where(Friend.friend_code == removed_friend_code).where(Friend.network == network))
                            session.execute(delete(DiscordFriends).where(
                                DiscordFriends.friend_code == removed_friend_code,
                                DiscordFriends.network == network)
                            )
                            session.commit()

                        if len(network_friends) > 0:
                            time.sleep(DELAY)
                            tracked_presences = await friends_client.get_friend_presence([ e.pid for e in network_friends ])
                            online_users = []
                            for game in tracked_presences:
                                # Set all to offline if scraping
                                if SCRAPE_ONLY:
                                    break

                                online_users.append(game.pid)
                                game_description = game.presence.game_mode_description
                                if not game_description:
                                    game_description = ''
                                joinable = bool(game.presence.join_availability_flag)

                                friend_code = str(
                                    love2.principal_id_to_friend_code(game.pid)
                                    ).zfill(12)
                                session.execute(
                                    update(Friend)
                                    .where(Friend.friend_code == friend_code)
                                    .where(Friend.network == network)
                                    .values(
                                        online=True,
                                        title_id=game.presence.game_key.title_id,
                                        upd_id=game.presence.game_key.title_version,
                                        joinable=joinable,
                                        game_description=game_description,
                                        last_online=time.time()
                                    )
                                )
                                session.commit()

                            for offline_user in [ h for h in rotation if not h in online_users ]:
                                friend_code = str(
                                    love2.principal_id_to_friend_code(offline_user)
                                    ).zfill(12)
                                session.execute(
                                    update(Friend)
                                    .where(Friend.friend_code == friend_code)
                                    .where(Friend.network == network)
                                    .values(
                                        online=False,
                                        title_id=0,
                                        upd_id=0
                                    )
                                )
                                session.commit()

                            # I just do not understand what I'm doing wrong with get_friend_mii_list
                            # The docs do not specify much
                            # And no matter how many trials I do with varying inputs, nothing works
                            # I do not give up, but until I figure it out, the slower method (get_friend_mii)
                            # will have to do.

                            for current_friend in network_friends:
                                work = False
                                for l in all_friends:
                                    if (l[0] == current_friend.pid and time.time() - l[1] <= 600000) or SCRAPE_ONLY:
                                        work = True
                                if not work:
                                    continue

                                time.sleep(DELAY)

                                current_friend.friend_code = 0 # A cursed (but operable) 'hack'
                                try:
                                    current_info = await friends_client.get_friend_persistent_info([current_friend.pid,])
                                except:
                                    continue
                                comment = current_info[0].message
                                favorite_game = 0
                                username = ''
                                face = ''
                                if not comment.endswith(' '):
                                    # Get user's mii + username from mii
                                    m = await friends_client.get_friend_mii([current_friend,])
                                    username = m[0].mii.name
                                    mii_data = m[0].mii.mii_data
                                    obj = love2.MiiData()
                                    obj.decode(obj.convert(io.BytesIO(mii_data)))
                                    face = obj.mii_studio()['data']

                                    # Get user's favorite game
                                    favorite_game = current_info[0].game_key.title_id
                                else:
                                    comment = ''

                                friend_code = str(
                                    love2.principal_id_to_friend_code(current_friend.pid)
                                    ).zfill(12)
                                session.execute(
                                    update(Friend)
                                    .where(Friend.friend_code == friend_code)
                                    .where(Friend.network == network)
                                    .values(
                                        username=username,
                                        message=comment,
                                        mii=face,
                                        favorite_game=favorite_game
                                    )
                                )
                                session.commit()

                        for friend in rotation + clean_up:
                            time.sleep(DELAY / QUICKER)
                            await friends_client.remove_friend_by_principal_id(friend)
            except Exception as e:
                print(f'An error occurred!\n {e}')
                print(traceback.format_exc())
                time.sleep(2)

        if SCRAPE_ONLY:
            print('Done scraping.')
            break

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '-n', '--network',
              choices=[member.lower_name() for member in NetworkType],
             required=True
             )
        args = parser.parse_args()

        network = NetworkType[args.network.upper()]

        if network != NetworkType.NINTENDO:
            # This delay is only needed for nintendo, and is unnessary for pretendo.
            DELAY, QUICKER = 0, 1

        start_db_time(datetime.datetime.now(), network)
        anyio.run(main)
    except (KeyboardInterrupt, Exception) as e:
        if network is not None:
            start_db_time(None, network)
        print(e)
