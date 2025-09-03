import argparse
import re
import copy
import yaml

import utility

"""
    "common_labels": {
        "KEY": {
            "regex": # regex
            "value": # static value
        }
    },
    "metrics": [
        {
            "id":
            "name":
            "type":
            "labels": {
                "KEY": {
                    "regex": # regex with one match
                    "value": # static value
                },
            ],
            "rules": {
                "regex": # regex with one match
                "op":    # set, add, subtract, increment, decrement
                "value': # static value
            }
        }
    ]
"""

# is loaded from command line argument
global_config = {}
file_config = {}

def init():
    # copy common labels into each metric
    if 'common_labels' in global_config:
        for metric in global_config['metrics']:
            if 'labels' not in metric:
                metric['labels'] = {}
            metric['labels'].update(global_config['common_labels'])

def callback(filename, data):
    # if we don't have config for this file setup, do that setup now
    if filename not in file_config:
        file_config[filename] = copy.deepcopy(global_config)

    # for each rule try to do something
    for metric in file_config[filename]['metrics']:
        name = metric['name']
        labelsDict = {} # needed to update metrics, collect as labels are updated

        # always set filename label
        #labelsDict['filename'] = filename

        if 'labels' in metric and metric['labels'] is not None:
            for key in metric['labels'].keys():
                label = metric['labels'][key]
                if 'regex' in label:
                    m = re.match(label['regex'], data)
                    if m is not None and m.groups() is not None and len(m.groups())>0 and m.groups()[0] is not None:
                        label['value'] = m.groups()[0].strip()
                if labelsDict is not None and 'value' in label:
                    labelsDict[key] = label['value']
                else:
                    # didn't have a value for a label, wipe the label dict (meaning we will not save a metric yet)
                    labelsDict = None

        # see if we can match any of the metric rules
        if 'rules' in metric:
            for rule in metric['rules']:
                value = None
                if 'value' in rule:
                    value = rule['value']
                matched = False
                if 'regex' in rule:
                    m = re.match(rule['regex'], data)
                    if m is not None:
                        # update value only if it's not set in config (hard coded)
                        matched = True
                        if value is None and m.groups() is not None and len(m.groups())>0 and m.groups()[0] is not None:
                            value = m.groups()[0].strip()

                # load cached value if we didn't find a match
                cached_value = None
                if 'cached_value' in rule:
                    cached_value = rule['cached_value']
                
                # if we do have a value but don't have all labels cache the value and bail
                if value is not None and labelsDict is None:
                    rule['cached_value'] = value
                    continue

                # and finally, only proceed if we have all label values and matched or have a cache
                if labelsDict is not None and (matched or cached_value is not None):    
                    # we have somtehing to do! yay.
                    op = rule['op']
                    if labelsDict is None:
                        rule['cached_value'] = value
                    else:
                        #print("{}({}, {}, {})".format(op,name,value,labelsDict))
                        #print("rule: {}".format(rule))
                        #print("data: {}".format(data))
                        if op == 'add' and value is not None:
                            # gauge
                            utility.add(name, float(value), labelsDict)
                        if op == 'set' and value is not None:
                            # gauge
                            utility.set(name, float(value), labelsDict)
                        if op == 'inc':
                            # counter
                            utility.inc(name, labelsDict)
                        if op == 'dec':
                            # counter
                            utility.dec(name, labelsDict)
                        
                        # wipe cached value if we have one
                        if 'cached_value' in rule:
                            rule['cached_value'] = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Export logs as prometheus metrics.")
    parser.add_argument("--port", type=int, help="port to expose metrics on")
    parser.add_argument("--config", type=str, help="log parsing configuration file")
    parser.add_argument("--logdir", type=str, help="base directory for target logs")
    parser.add_argument("--logfileregex", type=str, help="regex to match a log filename")
    
    args = parser.parse_args()
    
    # Start up the server to expose the metrics.
    utility.metrics(args.port)

    # load configuration
    with open(args.config, 'r') as f:
        global_config = yaml.load(f, Loader=yaml.FullLoader)
    
    # initialize 
    init()
    while True:
        utility.watchDirectory(args.logdir, args.logfileregex, 2, callback)

# python log-exporter.py --config log-exporter-nina.yaml --port 8001 --logdir "." --logfileregex test1.log