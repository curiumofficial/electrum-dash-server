#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2011 thomasv@gitorious
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from itertools import imap
import threading
import time
import hashlib
import struct

__b58chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
__b58base = len(__b58chars)

global PUBKEY_ADDRESS
global SCRIPT_ADDRESS
PUBKEY_ADDRESS = 0
SCRIPT_ADDRESS = 5

def rev_hex(s):
    return s.decode('hex')[::-1].encode('hex')


Hash = lambda x: hashlib.sha256(hashlib.sha256(x).digest()).digest()


hash_encode = lambda x: x[::-1].encode('hex')


hash_decode = lambda x: x.decode('hex')[::-1]


def header_to_string(res):
    pbh = res.get('prev_block_hash')
    if pbh is None:
        pbh = '0'*64

    return int_to_signed_long_bytes_hex(res.get('version')) \
        + rev_hex(pbh) \
        + rev_hex(res.get('merkle_root')) \
        + int_to_unsigned_long_bytes_hex(int(res.get('timestamp'))) \
        + int_to_unsigned_long_bytes_hex(int(res.get('bits'))) \
        + int_to_unsigned_long_bytes_hex(int(res.get('nonce')))


def _bytes_unpacker_for_number_format(format):
    unpack = struct.Struct(format).unpack

    def unpack_and_normalize(s):
        return unpack(s)[0]

    return unpack_and_normalize


signed_long_from_bytes = _bytes_unpacker_for_number_format("<l")
unsigned_long_from_bytes = _bytes_unpacker_for_number_format("<L")
unsigned_long_long_from_bytes = _bytes_unpacker_for_number_format("<Q")


def _int_to_bytes_converters_for_number_format(format):
    pack = struct.Struct(format).pack

    def pack_and_convert_to_hex(i):
        return pack(i).encode('hex')

    return pack, pack_and_convert_to_hex


int_to_signed_long_bytes, int_to_signed_long_bytes_hex = _int_to_bytes_converters_for_number_format('<l')
int_to_unsigned_long_bytes, int_to_unsigned_long_bytes_hex = _int_to_bytes_converters_for_number_format('<L')
int_to_unsigned_long_long_bytes, int_to_unsigned_long_long_bytes_hex = _int_to_bytes_converters_for_number_format('<Q')


def header_from_string(s):
    return {
        'version': signed_long_from_bytes(s[0:4]),
        'prev_block_hash': hash_encode(s[4:36]),
        'merkle_root': hash_encode(s[36:68]),
        'timestamp': unsigned_long_from_bytes(s[68:72]),
        'bits': unsigned_long_from_bytes(s[72:76]),
        'nonce': unsigned_long_from_bytes(s[76:80]),
    }


############ functions from pywallet #####################



def hash_160(public_key):
    try:
        md = hashlib.new('ripemd160')
        md.update(hashlib.sha256(public_key).digest())
        return md.digest()
    except:
        import ripemd
        md = ripemd.new(hashlib.sha256(public_key).digest())
        return md.digest()


def public_key_to_pubkey_address(public_key):
    return hash_160_to_pubkey_address(hash_160(public_key))


def public_key_to_bc_address(public_key):
    """ deprecated """
    return public_key_to_pubkey_address(public_key)


def hash_160_to_pubkey_address(h160, addrtype=None):
    """ deprecated """
    if not addrtype:
        addrtype = PUBKEY_ADDRESS
    return hash_160_to_address(h160, addrtype)


def hash_160_to_pubkey_address(h160):
    return hash_160_to_address(h160, PUBKEY_ADDRESS)


def hash_160_to_script_address(h160):
    return hash_160_to_address(h160, SCRIPT_ADDRESS)


def hash_160_to_address(h160, addrtype = 0):
    """ Checks if the provided hash is actually 160bits or 20 bytes long and returns the address, else None
    """
    if h160 is None or len(h160) is not 20:
        return None
    vh160 = chr(addrtype) + h160
    h = Hash(vh160)
    addr = vh160 + h[0:4]
    return b58encode(addr)

def bc_address_to_hash_160(addr):
    if addr is None or len(addr) is 0:
        return None
    bytes = b58decode(addr, 25)
    return bytes[1:21] if bytes is not None else None


def b58encode(v):
    """encode v, which is a string of bytes, to base58."""

    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
        long_value += (256**i) * ord(c)

    result = ''
    while long_value >= __b58base:
        div, mod = divmod(long_value, __b58base)
        result = __b58chars[mod] + result
        long_value = div
    result = __b58chars[long_value] + result

    # Bitcoin does a little leading-zero-compression:
    # leading 0-bytes in the input become leading-1s
    nPad = 0
    for c in v:
        if c == '\0':
            nPad += 1
        else:
            break

    return (__b58chars[0]*nPad) + result


def b58decode(v, length):
    """ decode v into a string of len bytes."""
    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
        long_value += __b58chars.find(c) * (__b58base**i)

    result = ''
    while long_value >= 256:
        div, mod = divmod(long_value, 256)
        result = chr(mod) + result
        long_value = div
    result = chr(long_value) + result

    nPad = 0
    for c in v:
        if c == __b58chars[0]:
            nPad += 1
        else:
            break

    result = chr(0)*nPad + result
    if length is not None and len(result) != length:
        return None

    return result


def EncodeBase58Check(vchIn):
    hash = Hash(vchIn)
    return b58encode(vchIn + hash[0:4])


def DecodeBase58Check(psz):
    vchRet = b58decode(psz, None)
    key = vchRet[0:-4]
    csum = vchRet[-4:]
    hash = Hash(key)
    cs32 = hash[0:4]
    if cs32 != csum:
        return None
    else:
        return key




########### end pywallet functions #######################
import os

def random_string(length):
    return b58encode(os.urandom(length))

def timestr():
    return time.strftime("[%d/%m/%Y-%H:%M:%S]")



### logger
import logging
import logging.handlers

logger = logging.getLogger('electrum')

def init_logger(logfile):
    hdlr = logging.handlers.WatchedFileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s %(message)s', "[%d/%m/%Y-%H:%M:%S]")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.INFO)


def print_log(*args):
    logger.info(" ".join(imap(str, args)))

def print_warning(message):
    logger.warning(message)


# profiler
class ProfiledThread(threading.Thread):
    def __init__(self, filename, target):
        self.filename = filename
        threading.Thread.__init__(self, target = target)

    def run(self):
        import cProfile
        profiler = cProfile.Profile()
        profiler.enable()
        threading.Thread.run(self)
        profiler.disable()
        profiler.dump_stats(self.filename)
