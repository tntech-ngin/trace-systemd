from datetime import datetime, timezone
import json
import logging
import os
import psutil
import random
import schedule
import sys
import subprocess
import time
import uuid

# Note: Mounts, privileges needed:
# "--network", "container:nfd",
# "-v", "${PWD}/dist/nlsr:/config",
# "-v", "<host-ssh-dir>:/root/.ssh:ro",
# "-v", "/home/ndnops/ndntdump-exp-2023:/dump",


# Constants
OUTPUT_DIR = "/dump"

# Set up logging
LOGGER = logging.getLogger("ANALYSER")
LOGGER.setLevel(logging.DEBUG)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)
LOGGER.addHandler(_console_handler)


def run_command(cmd, child=False):
    if child:
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setpgrp
        )
    return subprocess.check_output(cmd, shell=True).decode().strip()


def construct_node_name():
    try:
        nlsr_info = run_command("infoconv info2json < ./nlsr.conf")
        nlsr_json = json.loads(nlsr_info)
        node_name = nlsr_json["general"]["site"].replace("/", "_").lstrip("_")
    except Exception as e:
        LOGGER.error(f"Error getting node name: {e}")
    if not node_name:
        node_name = str(uuid.uuid4())
    return node_name


def stop_ndntdump():
    for proc in psutil.process_iter():
        if "ndntdump" in proc.name():
            LOGGER.info(f"Terminating ndntdump process: {proc.pid}")
            proc.terminate()
            proc.wait(timeout=10)


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
    try:
        cmd = f'scp -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oProxyCommand="ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -W %h:%p ndntraces@orion.ngin.tntech.edu" {OUTPUT_DIR}/*.zst ndntraces@10.20.10.30:/raid/tracedata/'
        success = run_command(cmd)
        if success == 0:  # Success
            run_command(f"rm -rf {OUTPUT_DIR}/*.zst")
    except Exception as e:
        LOGGER.error(f"Error copying ndntdump files: {e}")


def schedule_tasks():
    schedule.every().day.at("17:00", "UTC").do(
        start_ndntdump
    )  # Start ndntdump at 5 PM UTC
    schedule.every().day.at("20:00", "UTC").do(
        stop_ndntdump
    )  # Stop ndntdump at 8 PM UTC

    # Randomly schedule SCP between 20:15 and 20:59 (8:15 PM to 8:59 PM UTC)
    random_minute = random.randint(15, 59)
    scp_time = f"20:{random_minute:02d}"
    schedule.every().day.at(scp_time, "UTC").do(scp_dump)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    schedule_tasks()
