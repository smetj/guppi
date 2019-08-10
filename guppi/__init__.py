#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  poc.py
#
#  Copyright 2018 Jelle Smet <development@smetj.net>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from gevent import socket
from gevent.server import StreamServer
from gevent.pool import Pool
from gevent import monkey
import os
import yaml
import subprocess
import argparse
import json
import importlib.util
import logging
import sys
import time

monkey.patch_all()


class ConfigReader:
    def __init__(self, config_path):

        self.config_path = config_path
        self.config = self.load()

        self.python_actions = {}
        self.shell_actions = {}
        self.prompt_function = self.__loadPythonFile(
            self.config["prompt"]["path"], self.config["prompt"]["name"]
        )

        for action in self.config["actions"]["python"]:
            if action["enabled"]:
                self.python_actions[action["name"]] = self.__pythonExec(
                    action["name"],
                    self.__loadPythonFile(action["path"], action["name"]),
                )

        for action in self.config["actions"]["shell"]:
            if action["enabled"]:
                self.shell_actions[action["name"]] = self.__shellExec(
                    action["name"], action["command"]
                )

        self.locks = []

    def load(self):
        """

        """

        with open(self.config_path, "r") as config:
            config = yaml.load(config)
        return config

    def __loadPythonFile(self, file_name, function_name):

        spec = importlib.util.spec_from_file_location(
            "_%s" % (function_name), file_name
        )
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        return getattr(foo, function_name)

    def __shellExec(self, name, command):
        def execute(event, env):
            if name in self.locks:
                logging.warning(
                    "Action '%s' is still running from a previous execution." % (name)
                )
                return
            else:
                self.locks.append(name)

            start_time = time.time()
            try:
                cmd = command.format(**event)
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
                )
                result.check_returncode()
            except Exception as err:
                logging.error(
                    "Failed to execute shell action '%s'. Reason: %s" % (name, err)
                )
            else:
                logging.info(
                    "Executing shell action '%s' took %0.2f seconds."
                    % (name, time.time() - start_time)
                )
                self.locks.remove(name)
                return result.stdout.decode("utf-8").rstrip()

        return execute

    def __pythonExec(self, name, function):
        def execute(event, env):
            start_time = time.time()
            try:
                result = function(event, env)
            except Exception as err:
                logging.error(
                    "Failed to execute python action '%s'. Reason: %s" % (name, err)
                )
            else:
                logging.info(
                    "Executing Python action '%s' took %0.2f seconds."
                    % (name, time.time() - start_time)
                )
                return result

        return execute


class Guppi(ConfigReader):
    """
    The Unix Domain Socket server listening to incoming connections.

    Args:
        socket_path (str): The location of the unix domain socket file.
        config_path (str): The location of the yaml config file.
    """

    def __init__(self, socket_path, config_path):

        self.socket_path = os.path.expanduser(socket_path)
        self.config_path = os.path.expanduser(config_path)

        ConfigReader.__init__(self, self.config_path)
        self.__setupLogging()

        self.exec_pool = Pool(500)

    def serve(self):
        """
        A blocking function which starts listening for incoming requests.
        """

        pool = Pool(100)
        sock = self.__get_socket_instance()
        self.stream_server = StreamServer(sock, self.__handle, spawn=pool)
        self.stream_server.serve_forever()

    def __get_socket_instance(self):
        """
        Returns a Unix Domain Socket instance object.

        Returns:
            socket.socket(): A unix domain socket instance object.
        """

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        listener.bind(self.socket_path)
        listener.listen(1)
        return listener

    def __handle(self, sock, address):
        """
        Is executed for each incoming request.

        Args:
            sock (socket.socket instance): The connection socket.
            address (None): None because unix domain socket listener
        """

        request = sock.recv(1024)
        try:
            event = json.loads(request)
        except Exception as err:
            logging.error("Failed to parse incoming payload. Reason: %s" % (err))
            return

        if self.config["prompt"]["enabled"]:
            try:
                sock.send(self.prompt_function(event, {}).encode("utf-8"))
            except Exception as err:
                logging.error("Failed to execute prompt action. Reason: %s" % (err))

        for name, function in self.python_actions.items():
            self.exec_pool.spawn(function, event, {})

        for name, function in self.shell_actions.items():
            self.exec_pool.spawn(function, event, {})

        sock.close()

    def __setupLogging(self):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)


def parse_args():
    """
    Parses CLI arguments

    Returns:
        argparse.Namespace: Contains the provider CLI args.
    """

    parser = argparse.ArgumentParser(
        description="A daemon to automate your shell environment."
    )
    parser.add_argument(
        "--socket",
        type=str,
        dest="socket",
        default="~/.guppi.socket",
        help="The unix domain socket file location on which guppi accepts input.",
    )
    parser.add_argument(
        "--config",
        type=str,
        dest="config",
        default="~/.guppi.yaml",
        help="The config file in YAML format containing guppi's configuration.",
    )
    return parser.parse_args()


def main():

    args = parse_args()
    cli_server = Guppi(socket_path=args.socket, config_path=args.config)
    try:
        cli_server.serve()
    except KeyboardInterrupt as err:
        del (err)
        print("Exit")


if __name__ == "__main__":
    main()
