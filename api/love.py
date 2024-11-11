"""
Created by Deltaion Lee (MCMi460) on Github
Convert `friendCode` into `principalId`

This method took two weeks to figure out and five minutes to code
Thank you, https://www.3dbrew.org/wiki/Principal_ID
for essentially making my efforts have worth
I would kiss Meleemeister (https://www.3dbrew.org/wiki/Special:Contributions/Meleemeister)
"""

# pylint: disable=function-redefined
# from . import *
import hashlib


class FriendCodeValidityError(Exception):
    pass


class PrincipalIDValidityError(Exception):
    pass


# Structure of a friendCode:
#
# (0x__ << 32) | 0x________
#   Checksum     PrincipalID
#

def friend_code_to_principal_id(friend_code: str) -> int:
    """
    return the principal id of a given friend code
    Ensure this friend code has no hyphens, just its 12 digits.
    @params friend_code a string that contain a 3ds friend code
    @return a integer that is the principal ID of the given friend code
    @throws FriendCodeValidityError raised when a invalid friend code was given
    """
    friend_code = ''.join(filter(str.isdigit, str(friend_code))).zfill(12)
    if len(friend_code) != 12:
        raise FriendCodeValidityError('an invalid friend code was passed')

    # Convert friend_code into hexadecimal
    checksum_principal = ('%08X' % int(friend_code)).zfill(10)
    # Remove most significant byte and convert to integer
    principal_id = int(checksum_principal[2:], 16)
    # Separate checksum from checksum_principal
    checksum_byte = hex(int(checksum_principal[:2], 16))
    if not check_principal_id_validity(checksum_byte, principal_id):
        raise FriendCodeValidityError('an invalid friend code was passed')

    return principal_id


def check_principal_id_validity(checksum_byte: str, principal_id: int) -> bool:
    return generate_checksum_byte(principal_id) == checksum_byte


# https://www.3dbrew.org/wiki/FRDU:PrincipalIdToFrien
def generate_checksum_byte(principal_id: int) -> str:
    # Little-endian SHA-1 of principal_id
    sha1 = hashlib.sha1(principal_id.to_bytes(4, byteorder='little'))
    # Shift first byte to the right by one
    return hex(int(sha1.hexdigest()[:2], 16) >> 1)


def principal_id_to_friend_code(principal_id: int) -> int:
    if not isinstance(principal_id, int):
        raise PrincipalIDValidityError('an invalid principal id was passed')

    checksum_byte = generate_checksum_byte(principal_id)
    friend_code = checksum_byte + hex(principal_id)[2:].zfill(8)
    return int(friend_code.replace('0x', ''), 16)
