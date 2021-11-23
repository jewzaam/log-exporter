# log-exporter

Watches log files and exports prometheus metrics.  Created to scrape logs from astrophotography software but it can be extended for other purposes.  The following software logs can be scraped, though beware this is not setup for 100% of use cases!  There can be gaps, PR's welcome.

* [NINA](https://nighttime-imaging.eu/) - open source astrophotography imaging suite
* Autofocus - logs from focusing using NINA (maybe they're standard structure?)
* [PHD2](https://openphdguiding.org/) - open source guiding software

## Setup

You don't need any environment specific settings, just decide what logs you want to export metrics from.

## Usage

Select the following:
* port - the port you'll export metrics on for scraping
* config - the config for the logs you want to export
* logdir - the directory in which the log files reside
* logfileregex - regular expression for the log filenames (allows for picking a subset)

Note if you want to scrape more than one directory with the same log exporter you need to run multiple instances.

Given that NINA is a windows application I do run this on windows.  So, the following makes that assumption.
```shell
python log-exporter.py --port 8001 --config config\log-exporter-nina.yaml --logdir "%LocalAppData%\NINA\Logs" --logfileregex ".*\.log"
python log-exporter.py --port 8002 --config config\log-exporter-autofocus.yaml --logdir "%LocalAppData%\NINA\AutoFocus" --logfileregex ".*\.json"
python log-exporter.py --port 8003 --config config\log-exporter-nina.yaml --logdir "%UserProfile%\Documents\PHD2" --logfileregex "PHD2_GuideLog.*[0-9]\.txt"
```

### NINA Setup

In NINA you need to turn **Debug** logging on to get cancellation and skipped events.  It appears debug isn't verbose but these logs will address if you cancel a sequence run in the middle of something like autofocus or skip camera cooling.

1. start NINA
2. go to "Options" tag
3. select "General" tag
4. under the "General" section, chaneg "Log level" to "Debug"

## Verify

In your favorite browser look at the metrics endpoint.  If it's local, you can use:
* http://localhost:8001
* http://localhost:8002
* http://localhost:8003

# Creating Log Exporters

It's as simple as creating a new config yaml file.  The structure of the file isn't too crazy and you have examples in the `config` dir for supported exporters.

Each of the exporters has a set of labels that are applied to all metrics.  **Beware** that metrics won't start exporting until these common labels have a value, so only use something that will *always* be present in a log file!

* `common_labels` - array of labels that are set for all metrics in this exporter
  * the key - the name of the metric and one of the following child properties
    * `regex` - regex with one match, the match becomes the value of the key
    * `value` - a static value

On startup you may want to clear some already exported metrics.  For example, in the nina exporter there are several gauges that are set to **0** on startup.

* `initialize` - array of initialization to run once at exporter startup.  Note this still requires all `common_labels` to have values.
  * `metric` - the metric in the form of a prometheus query
  * `type` - either **gauge** or **counter**
  * `value` - the value to set the metric to

Finally we get to the list of metrics!  Each has a name, some rules, and a type.  You can choose to add labels, but they're not required.  All metrics inhert iabels from `common_labels`.

* `metrics` - array of all metric configurations
  * `name` - name of the metric
  * `rules` - array of rules to set when all critera (labels) are met
    * `op` - operator to apply, one of
      * **add** - add the value or regex match to the metric
      * **dec** - decrement the metric value by 1
      * **inc** - increment the metric value by 1
      * **set** - set the metric value to the value or regex match
    * `regex` - a regex that must match for the rule to apply.  Note a regex group is only required if no `value` is specified.
    * `value` - a static value to use for the rule operation. Required for **add** and **set** if `regex` is not used or `regex` does not have a group.
  * `type` - either **gauge** or **counter**
  * `labels` - optional array of labels to apply to the metric.  All labels must have a value before rules are applied, else it doesn't 'fire'.
    * **label name** - whatever the metric's name is
      * `regex` - a regex with one match, cannot be used with `value`
      * `value` - a static value for the label, cannot be used with `regex`

## Example: common_labels

Create a label **profile** on all metrics where the value comes from a regex:

```yaml
common_labels:
  profile:
    regex: ^Equipment Profile = (.+)
```

## Example: initialize

Reset nina status metric for "MessageBox" to 0 on startup of the exporter:

```yaml
initialize:
- metric: nina_status{category="Utility",item="MessageBox"}
  type: gauge
  value: 0
```

## Examples: metrics

There are a lot of examples in the `config\` directory.  This just illustrates a few.

A "total" counter for phd2, matches on all log lines and increments the counter metric:

```yaml
- labels:
    type:
      value: "all"
  name: phd2_total
  rules:
  - op: inc
    regex: .*
  type: counter
```

Set phd2 Guiding status based on log lines, but set a static value:

```yaml
- labels:
    status:
      value: Guiding
  name: phd2_status
  rules:
  - op: set
    regex: ^Guiding Ends.*
    value: 0
  - op: set
    regex: ^Guiding Begins.*
    value: 1
  type: gauge
```

Add pulse guiding corrections in phd2 with the **direction** label set to the correction direction of either 'N' or 'S':

```yaml
- labels:
    direction:
      regex: ^[0-9]*,.*,[0-9]*,([NS]),.*
  name: phd2_pulse
  rules:
  - op: add
    regex: ^[0-9]*,.*,([0-9]+),[NS],.*
  type: gauge
```

# Troubleshooting

## No metrics are exported

If you are using `common_labels` make sure any regex are satisifed by a log line.  If not, this will block all metrics from being exported.