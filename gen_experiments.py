#! /usr/bin/env python3
import sys
import copy
import traceback
import os
import os.path
import tempfile
import subprocess
import itertools
import shutil
import glob
import signal
import shutil

from argparse import ArgumentParser
from logging import info, debug, error

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from pylib.placement_strategy import ClientPlacement, BalancedPlacementStrategy, LeaderPlacementStrategy

import logging
import yaml

TMP_DIR='./tmp'
FINAL_DIR='./dsef'

logger = logging.getLogger('')

def gen_experiment_suffix(b, m, c, z, cl):
    m = m.replace(':', '-')
    if z is not None:
        return "{}_{}_{}_{}_{}".format(b, m, c, z, cl)
    else:
        return "{}_{}_{}_{}".format(b, m, c, cl)

def gen_process_and_site(args, experiment_name, num_c, num_s, num_replicas, hosts_config, mode):

    layout_strategies = {
        ClientPlacement.BALANCED: BalancedPlacementStrategy(),
        ClientPlacement.WITH_LEADER: LeaderPlacementStrategy(),
    }

    if False and mode.find('multi_paxos') >= 0:
        strategy = layout_strategies[ClientPlacement.WITH_LEADER]
    else:
        strategy = layout_strategies[ClientPlacement.BALANCED]

    layout = strategy.generate_layout(args, num_c, num_s, num_replicas, hosts_config)

    if not os.path.isdir(TMP_DIR):
        os.makedirs(TMP_DIR)

    if not os.path.isdir(FINAL_DIR):
        os.makedirs(FINAL_DIR)

    site_process_file = tempfile.NamedTemporaryFile(
        mode='w',
        prefix='janus-proc-{}'.format(experiment_name),
        suffix='.yml',
        dir=TMP_DIR,
        delete=False)

    contents = yaml.dump(layout, default_flow_style=False)

    result = None
    with site_process_file:
        site_process_file.write(contents)
        result = site_process_file.name

    return result

def load_config(fn):
    with open(fn, 'r') as f:
        contents = yaml.load(f)
        return contents

def modify_dynamic_params(args, benchmark, mode, abmode, zipf):
    configs = args["other_config"]
    configs.append("config/{}.yml".format(benchmark))

    if "{}:{}".format(mode, abmode) == "tapir:tapir": configs.append("config/tapir.yml")
    elif "{}:{}".format(mode, abmode) == "brq:brq": configs.append("config/brq.yml")
    elif "{}:{}".format(mode, abmode) == "occ:multi_paxos": configs.append("config/occ_paxos.yml")
    return [load_config(fn) for fn in configs]

def aggregate_configs(*args):
    config = {}
    for fn in args:
        config.update(fn)
    return config

def generate_config(args, hosts, experiment_name, benchmark, mode, zipf, client_load, num_client,
                    num_server, num_replicas):
    logger.debug("generate_config: {}, {}, {}, {}, {}".format(
        experiment_name, benchmark, mode, num_client, zipf))
    # hosts_config = load_config(args["hosts_file"])
    hosts_config = hosts
    proc_and_site_config = gen_process_and_site(args, experiment_name,
                                                num_client, num_server,
                                                num_replicas, hosts_config, mode)

    logger.debug("site and process config: %s", proc_and_site_config)
    cc_mode, ab_mode = mode.split(':')
    config = modify_dynamic_params(args, benchmark, cc_mode, ab_mode,
                                         zipf)
    config.insert(0, hosts_config)
    config.append(load_config(proc_and_site_config))
    result = aggregate_configs(*config)

    if result['client']['type'] == 'open':
        if client_load == -1:
            logger.fatal("must set client load param for open clients")
            sys.exit(1)
        else:
            result['client']['rate'] = client_load

    with tempfile.NamedTemporaryFile(
            mode='w',
            prefix='janus-final-{}-'.format(args["name"]),
            suffix='.yml',
            dir=FINAL_DIR,
            delete=False) as f:
        f.write(yaml.dump(result))
        result = f.name.split("/")[-1]
        logger.info("result: %s", result)
    return os.path.join('dsef', result)

def generate(conf, hosts):
    experiment_suffix = gen_experiment_suffix(
        conf['benchs'],
        conf['protocols'],
        conf['clients'],
        conf['zipf'],
        conf['client_loads'])
    experiment_name = "{}-{}".format(conf['name'], experiment_suffix)

    logger.info("Experiment: {}".format(experiment_name))
    config_file = generate_config(
        conf,
        hosts,
        experiment_name,
        conf['benchs'], conf['protocols'],
        conf['zipf'],
        conf['client_loads'],
        conf['clients'],
        conf['servers'],
        conf['shards'])

    conf.update({'config_file':config_file})

def print_args(args):
    for k,v in args.items():
        logger.debug("%s = %s", k, v)

def main(conf, hosts):
    logging.basicConfig(format="%(levelname)s : %(message)s")
    logger.setLevel(logging.DEBUG)

    files = []
    files.append("config/{}.yml".format(conf['client_type']))
    files.append("config/concurrent_{}.yml".format(conf['concurrent']))
    conf.update({"other_config":files})

    print_args(conf)
    try:
        generate(conf, hosts)
        shutil.rmtree(TMP_DIR)
    except Exception:
        traceback.print_exc()
