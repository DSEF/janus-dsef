#!/usr/bin/env python3

import rpyc
import subprocess
import os
import signal
from time import sleep
import sys
from gen_experiments import main as gen
import copy
from pydsef import Service, experiment, Registry

NUM_TRIES = 10

@Registry.experiment
class WrapperService(Service):

    @Registry.setup
    def setup(self, ed, hosts):
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

    @Registry.launch
    def launch(self):
        self.root.launch()

    @Registry.run
    def run(self):
        return self.root.run()

    @Registry.teardown
    def teardown(self):
        self.root.teardown()

        self.conn.close()
        self.root = None
        self.run_process.kill()
