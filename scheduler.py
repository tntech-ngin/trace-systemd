from datetime import datetime, timezone
import json
import logging
import os
import psutil
import schedule
import sys
import subprocess
import time
import uuid

# Note: Mounts, privileges needed:
# "--network", "host",
# "-v", "${PWD}/dist/nlsr:/config",
# "-v", "<host-ssh-dir>:/root/.ssh:ro",

# Constants
OUTPUT_DIR = "/dump"

# Set up logging
LOGGER = logging.getLogger("ANALYSER")
LOGGER.setLevel(logging.DEBUG)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
LOGGER.addHandler(_console_handler)


def run_command(cmd, child=False):
    # Exclude shell parameter
    if child:
        return subprocess.Popen(cmd, shell=True)
    return subprocess.check_output(cmd, shell=True).decode().strip()


def construct_node_name():
    try:
        nlsr_info = run_command('infoconv info2json < ./nlsr.conf')
        nlsr_json = json.loads(nlsr_info)
        node_name = nlsr_json['general']['site'].replace('/', '_').lstrip('_')
    except Exception as e:
        LOGGER.error(f"Error getting node name: {e}")
    if not node_name:
        node_name = str(uuid.uuid4())
    return node_name


def stop_ndntdump():
    for proc in psutil.process_iter():
        if "ndntdump" in proc.name():
            proc.kill()
            LOGGER.info(f"Killed ndntdump process: {proc.pid}")


def start_ndntdump():
    # Stop any existing ndntdump process
    stop_ndntdump()

    # Start new ndntdump process
    node = construct_node_name()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cmd = f'ndntdump --ifname "*" -w {OUTPUT_DIR}/{node}-{date}.pcapng.zst'
        proc = run_command(cmd, child=True)
        LOGGER.info(f"Started ndntdump process: {proc.pid}")
    except Exception as e:
        LOGGER.error(f"Error starting ndntdump: {e}")


def scp_dump():
    # look at ssh lib (paramiko)
    try:
        cmd = f'scp -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oProxyCommand="ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -W %h:%p ndntraces@orion.ngin.tntech.edu" {OUTPUT_DIR}/*.zst ndntraces@10.20.10.30:/raid/tracedata/'
        success = run_command(cmd)
        if success == 0: # Success
            run_command(f'rm -rf {OUTPUT_DIR}/*.zst')
    except Exception as e:
        LOGGER.error(f"Error copying ndntdump files: {e}")


def schedule_tasks():
    # TODO: Use UTC time
    schedule.every().day.at("05:00").do(start_ndntdump)
    schedule.every().day.at("08:00").do(stop_ndntdump)
    # Random schedule for scp by different nodes
    schedule.every().day.at("08:15").do(scp_dump)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    # schedule_tasks()
    start_ndntdump()
    stop_ndntdump()