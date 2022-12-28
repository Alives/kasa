#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import json
import logging
import socket
import sys
import time
from struct import pack

sys.path.append('/opt/repos/mypylib')
from mypylib import setup_logging


def encrypt(string):
  key = 171
  result = pack('>I', len(string))
  for i in string:
    a = key ^ ord(i)
    key = a
    result += bytes([a])
  return result

def decrypt(string):
  key = 171
  result = ''
  for i in string:
    a = key ^ i
    key = i
    result += chr(a)
  return result

def setup_socket(ip):
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(1)
  sock.connect((ip, SMARTPLUG_PORT))
  logging.info('Connected to smartplug at %s', ip)
  return sock

def query_smartplug(sock):
  sock.send(COMMANDS['sysinfo'])
  str_data = sock.recv(2048)
  decrypted = decrypt(str_data[4:])
  data = json.loads(decrypted)
  relay_state = data['system']['get_sysinfo']['relay_state']
  return relay_state

def set_state(ip, desired_state):
  logging.info('Setting follower smartplug relay state to %d.', desired_state)
  sock = setup_socket(ip)
  sock.send(COMMANDS['state'][desired_state])
  sock.close()
  logging.info('Done.')

setup_logging('/var/log/cron/plug_tracker.log')
# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'state': {
      0: encrypt('{"system":{"set_relay_state":{"state":0}}}'),
      1: encrypt('{"system":{"set_relay_state":{"state":1}}}'),
    },
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

SMARTPLUG_PORT = 9999

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--follower', required=True,
                    help='Smartplug hostname or IP address acting as follower.')
parser.add_argument('-l', '--leader', required=True,
                    help='Smartplug hostname or IP address acting as leader.')
args = parser.parse_args()

while True:
  try:
    sock = setup_socket(args.leader)
  except:
    logging.error('Could not connect to host %s', args.leader)
    time.sleep(1)
    continue
  break

prev_state = -1
while True:
  try:
    relay_state = query_smartplug(sock)
  except:
    sock = setup_socket(args.leader)
    continue
  if relay_state != prev_state and prev_state != -1:
    set_state(args.follower, relay_state)
  prev_state = relay_state
  time.sleep(1)
