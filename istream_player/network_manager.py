import json
import logging
import socket
import subprocess
from pprint import pprint
from threading import Thread
from time import sleep, time
from typing import List

from istream_player.analyzers.exp_events import ExpEvent_BwSwitch
from istream_player.analyzers.exp_recorder import ExpWriter

IF_NAME = "eth0"
NETEM_LIMIT = 1000


class NetworkConfig:
    def __init__(self, bw, latency, drop, sustain, recorder, log, server_container, target_ip):
        self.bw = bw
        self.latency = latency
        self.drop = drop
        self.sustain = sustain
        self.recorder: ExpWriter = recorder
        self.log = log
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.target_ip = target_ip
        self.server_container = server_container
        self.log.info(f"Server Container: {self.server_container}")
        # while True:
        #     self.log.info(f"Blocked")
        #     sleep(1)

    def run_in_container(self, script):
        # self.server_socket.sendall(script.encode())
        cmd = ["docker", "exec", self.server_container['ID'], "bash", "-c", script]
        subprocess.check_call(cmd, stderr=subprocess.STDOUT)
        self.log.info("Running inside container: " + " ".join(cmd))

    def run_on_host(self, script):
        subprocess.check_call(script, shell=True, executable="/bin/bash", stderr=subprocess.STDOUT)
        self.log.info("Running on host: " + script)

    def apply(self, if_name):
        script = f'''
        set -e
        tc qdisc change dev {if_name} handle 2: tbf rate {self.bw}kbit limit 10000 burst 2000
        tc qdisc change dev {if_name} handle 3: netem limit {NETEM_LIMIT} delay {self.latency}ms 0ms loss {float(self.drop) * 0:.3f}%
        '''
        t = round(time() * 1000)
        self.run_in_container(script)
        self.recorder.write_event(ExpEvent_BwSwitch(t, float(self.bw), float(self.latency), float(self.drop)))

    def setup(self, if_name):
        script = f'''
        set -e
        tc qdisc del dev {if_name} root || true
        tc qdisc add dev {if_name} root handle 1: prio
        tc qdisc add dev {if_name} parent 1:3 handle 2: tbf rate {self.bw}kbit limit 10000 burst 2000
        tc qdisc add dev {if_name} parent 2:1 handle 3: netem limit {NETEM_LIMIT} delay {self.latency}ms 0ms loss {float(self.drop) * 0:.3f}%
        tc filter add dev {if_name} protocol ip parent 1:0 prio 3 u32 match ip dst {self.target_ip} flowid 1:3
            '''
        self.run_in_container(script)


class NetworkManager:
    log = logging.getLogger("NetworkManager")

    def __init__(self, bw_profile_path: str, recorder: ExpWriter):
        self.client_ip = None
        self.current_container = None
        self.server_container = None
        self.force_stop = False
        self.bw_profile_path = bw_profile_path
        self.delay = 1
        self.timeline: List[NetworkConfig] = []
        self.recorder = recorder
        self.get_server_container()
        self.get_client_ip()

        with open(bw_profile_path) as f:
            last_line = ""
            for line in f:
                if line == last_line:
                    self.timeline[-1].sustain += self.delay
                    continue
                last_line = line
                [bw, latency, drop] = line.strip().split(" ")
                self.timeline.append(NetworkConfig(bw, latency, drop, self.delay, self.recorder, log=self.log,
                                                   server_container=self.server_container, target_ip=self.client_ip))

    def get_server_container(self):
        self.current_container = json.loads(subprocess.check_output(
            'docker ps --format \'{"ID":"{{ .ID }}", "Image": "{{ .Image }}", "Names":"{{ .Names }}"}\' --filter id=$(cat /etc/hostname)',
            shell=True, executable="/bin/bash"))
        if not self.current_container["Names"].endswith("-client-1"):
            pprint(self.current_container)
            raise Exception("Failed to get current container")
        docker_compose_proj = self.current_container["Names"][:-len("-client-1")]
        server_container_name = docker_compose_proj + "-server-1"
        self.server_container = json.loads(subprocess.check_output(
            'docker ps --format \'{"ID":"{{ .ID }}", "Image": "{{ .Image }}", "Names":"{{ .Names }}"}\' --filter name=' + server_container_name,
            shell=True, executable="/bin/bash"))
        if not self.current_container["Names"].endswith("-client-1"):
            pprint(self.current_container)
            raise Exception("Failed to get server container")

    def get_client_ip(self):
        assert self.server_container is not None
        self.client_ip = subprocess.check_output(["docker", "exec", self.server_container["ID"], "bash", "-c", "dig +short client"]).decode().strip()
        self.log.info(f"Detected current container IP: {self.client_ip}")

    def start(self, if_name):
        for config in self.timeline:
            config.apply(if_name)
            self.log.info(f"Sustain Network Config for {config.sustain} seconds")
            for s in range(config.sustain):
                if self.force_stop:
                    return
                sleep(1)

    def start_bg(self):
        # if_name = subprocess.check_output(f'''
        # grep -l $(docker exec {os.environ["CONTAINER"]} bash -c 'cat /sys/class/net/eth0/iflink' | tr -d '\\r') /sys/class/net/veth*/ifindex | sed -e 's;^.*net/\\(.*\\)/ifindex$;\\1;'
        # ''', shell=True, executable="/bin/bash", stderr=subprocess.STDOUT).decode().strip()
        if_name = "eth0"
        self.timeline[0].setup(if_name)
        self.log.info("Starting Network Manager in background")
        t = Thread(target=self.start, args=[if_name], daemon=True)
        t.start()

    def stop_bg(self):
        self.log.info("Stopping Network Manager in background")
        assert self.server_container is not None
        self.force_stop = True
        subprocess.check_call(["docker", "exec", self.server_container["ID"], "bash", "-c", "kill -s SIGINT 1"])
        pass
