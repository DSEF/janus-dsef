#!/usr/bin/env python3

import rpyc
import subprocess
import os
import signal
from time import sleep
import sys
from gen_experiments import main as gen
import copy

NUM_TRIES = 10

class WrapperService(rpyc.Service):
    def on_connect(self):
        pass

    def on_disconnect(self):
        pass

    def exposed_setup(self, ed, hosts):
        ed = copy.deepcopy(ed)
        hosts = copy.deepcopy(hosts)
        self.run_process = subprocess.Popen(['./dsef/run.py'])

        self.conn = None
        i = 0
        while self.conn == None:
            try:
                self.conn = rpyc.connect('localhost', 18860, config={'sync_request_timeout':60, 'allow_pickle':True})
                break
            except ConnectionRefusedError:
                if i < NUM_TRIES:
                    print("Failed to connect to run.py, trying again")
                    sleep(0.5)
                else:
                    print("Failed to connect. Aborting!")
                    raise ConnectionError
            i += 1

        self.root = self.conn.root
        print('Connected to process: {}'.format(self.run_process.pid))

        gen(ed, hosts)
        self.root.setup(ed, hosts)

    def exposed_launch(self):
        self.root.launch()

    def exposed_run(self):
        return self.root.run()

    def exposed_teardown(self):
        self.root.teardown()

        self.conn.close()
        self.root = None
        self.run_process.kill()

if __name__ == "__main__":
    from rpyc.utils.server import *
    t = ThreadedServer(WrapperService, port = 18861, protocol_config = {'allow_pickle':True})
    print("Starting RPyC Server...")
    t.start()
