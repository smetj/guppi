# guppi
A daemon to automate your shell environment

## Introduction

Guppi is a daemon which listens for incoming JSON formatted events. For each
event Guppi can execute a set of predefined Python scripts or shell commands.
The functionality these scripts and commands are left up to the user.

Submitting events in Guppi is done to its Unix domain socket and can be
automated in different ways such as:

  - Bash's `PROMPT_COMMAND` (http://tldp.org/HOWTO/Bash-Prompt-HOWTO/x264.html)
  - Bash-preexec (https://github.com/rcaloras/bash-preexec)
  - Zsh's hook functions (http://zsh.sourceforge.net/Doc/Release/Functions.html#Hook-Functions)
  - ... probably many more (let me know I'm curious!)

## Installation

Although it's optional, it's highly recommended to install Guppi in a
virtualenv so it doesn't clutter your default OS Python. Guppi requires
Python3.

The following steps are merely a guideline. You can install Guppi to the
location which makes most sense for you.

### Virtualenv (optional)
Install a virtualenv:

```$ python3 -m venenv ~/.guppi_python_venv```

Activate the virtualenv so when you invoke pip, it will install Guppi in the
newly created virtualenv:

```$ source ~/.guppi_python_venv/bin/activate```

Check if `python` points to the correct interpreter:

```
$ which python
~/.guppi_python_venv/bin/python
```

### Guppi

Installing Guppi can be done using pip:

```
$ python -m pip install guppi
```

Once installed you should have the `guppi` executable available:

```
$ guppi --help
usage: guppi [-h] [--socket SOCKET] [--config CONFIG]

A daemon to automate your shell environment.

optional arguments:
  -h, --help       show this help message and exit
  --socket SOCKET  The unix domain socket file location on which guppi accepts
                   input.
  --config CONFIG  The config file in YAML format containing guppi's
                   configuration.
```

### Executing Guppi without activating virtualenv first
In case virtualenv is used then `guppi` can be executed without activating its
virtualenv by executing:

```$ ~/.guppi_python_venv/bin/guppi```

### Starting Guppi on startup using systemd (optional)

In case your OS is using systemd and you'd like guppi to start automatically
then create the following unit file:

`~/.config/systemd/user/guppi.service`


```
[Unit]
Description=A deaemon to automate your shell environment

[Service]
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
ExecStart=~/.guppi_python_venv/bin/guppi
```

Once the unit file is created systemd needs to be reloaded:

```
$ systemctl --user daemon-reload
```

To start/stop/restart the Guppi daemon:
```
$ systemctl --user start guppi
```

To read Guppi logs from journald:
```
$ journalctl --user -xf -u guppi
```

## Guppi configuration

If `--config` hasn't been defined a configuration file is expected at
`~/.guppi.yaml`.

## Submitting events to Guppi

### Manually
```
$ echo '{\"pwd\": \"$(pwd)\"}' | nc  -U ~/.guppi.socket
```

### By setting PROMPT_COMMAND

The content of this variable is executed as a regular Bash command just before
Bash displays a prompt. See http://tldp.org/HOWTO/Bash-Prompt-HOWTO/x264.html
for more information.

You can set the value of `PROMPT_COMMAND` in `.bashrc`.

For example:

```
PROMPT_COMMAND='echo {\"pwd\":\"$(pwd)\", \"user\": \"$USER\", \"tmux_pane\": \"$TMUX_PANE\", \"python\": \"$(which python)\"}| nc -U ~/.guppi.socket'
```

## Configuring Guppi

consider following example

```yaml
    actions:
      python:
        - enabled: true
          name: setTmuxWindowTitle
          path: ~/.guppi/set_tmux_window_title.py

      shell:
        - enabled: true
          name: sleeper
          command: sleep 10

    prompt:
      enabled: true
      name: setPrompt
      path: ~/.guppi/set_prompt.py
```

There are 2 types of *actions* which can be executed:
  - a Python function
  - a Shell command

### Python actions

The `actions.python` key is a list which contains a number of Python functions
to execute. Each entry has 3 values:

   - `enabled`: Enables/disables the execution of the defined action.
   - `path`: The path containing the function to execute.
   - `name`: The name of the function to load and executed from `path`.
     The name is also used in logging.

A function should accept 2 parameters:

```
def doSomething(event, env):

    print(event)
```

Data returned by Python functions are ignored. Parameter `event` is the
submitted JSON event.  `env` is not used yet at the moment and is reserved for
future use.

### Shell actions

The `actions.shell` key is a list which contains a number of Python functions
to execute. Each entry has 3 values:

   - `enabled`: Enables/disables the execution of the defined action.
   - `command`: The command to execute.
   - `name`: A name given to the function used in logging.

`command` is a template string which can be rendered using the content of
*event* by using the Python `str.format` syntax.

### prompt

The `prompt` key defines a function which output can be used to render the
prompt. Only one can be defined.  It functions in the same way as a
`action.python` entry with a difference it's output is send back to the client
submitting the event.

# Setting prompt

You can set the prompt by assigning the response `nc` receives when submitting
the JSON event to Guppi to the `PS1` variable:

```
PROMPT_COMMAND='export PS1=$(echo $(echo {\"pwd\":\"$(pwd)\", \"user\": \"$USER\", \"tmux_pane\": \"$TMUX_PANE\", \"python\": \"$(which python)\"}| nc -U ~/.guppi.socket)"")'
```

As you notice this syntax is somewhat precarious.  If you have a better
approach please let me know.

# Support

For support just open a Github issue (https://github.com/smetj/guppi/issues)
with tag *question* or by sending me a msg on my Twitter handle
[@smetj](https://twitter.com/smetj).
