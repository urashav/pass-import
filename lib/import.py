#!/usr/bin/env python3
# pass import - Password Store Extension (https://www.passwordstore.org/)
# Copyright (C) 2017 Alexandre PUJOL <alexandre@pujol.io>.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import csv
from xml.etree import ElementTree
from subprocess import Popen, PIPE, list2cmdline
from collections import OrderedDict

if 'VERBOSE' not in os.environ or 'QUIET' not in os.environ:
    print("This program should only be called by 'pass import'.")
    exit(1)

VERBOSE = bool(int(os.environ['VERBOSE']))
QUIET = bool(int(os.environ['QUIET']))

GREEN = '\033[32m'
YELLOW = '\033[33m'
BRED = '\033[91m'
BGREEN = '\033[92m'
BYELLOW = '\033[93m'
BMAGENTA = '\033[95m'
BOLD = '\033[1m'
END = '\033[0m'

importer_map = {
    '1password': 'OnePassword',
    'chrome': 'Chrome',
    'dashlane': 'Dashlane',
    'enpass': 'Enpass',
    'fpm': 'FigaroPM',
    'gorilla': 'Gorilla',
    'kedpm': 'Kedpm',
    'keepass': 'Keepass',
    'keepasscsv': 'KeepassCSV',
    'keepassx': 'KeepassX',
    'kwallet': 'Kwallet',
    'lastpass': 'Lastpass',
    'passwordexporter': 'PasswordExporter',
    'pwsafe': 'Pwsafe',
    'revelation': 'Revelation',
    'roboform': 'Roboform'
}

def verbose(msg):
    if VERBOSE:
        print("%s  .  %s%s" % (BMAGENTA, END, msg))

def message(msg):
    if not QUIET:
        print("%s  .  %s%s" % (BOLD, END, msg))

def msg(msg):
    if not QUIET:
        print("       %s" % msg)

def success(msg):
    if not QUIET:
        print("%s (*) %s%s%s%s" % (BGREEN, END, GREEN, msg, END))

def warning(msg):
    if not QUIET:
        print("%s  w  %s%s%s%s" % (BYELLOW, END, YELLOW, msg, END))

def error(msg):
    print("%s [x] %s%sError: %s%s" % (BRED, END, BOLD, END, msg))

def die(msg):
    error(msg)
    exit(1)

class PasswordStoreError(Exception):
    pass

class PasswordStore():
    """ Simple Password Store for python, only able to insert password.
        Supports all the environnement variables.
    """
    def __init__(self):
        self.passbinary = "/usr/bin/pass"
        self.env = dict(**os.environ)
        self._setenv('PASSWORD_STORE_DIR', 'PREFIX')
        self._setenv('PASSWORD_STORE_KEY')
        self._setenv('PASSWORD_STORE_GIT', 'GIT_DIR')
        self._setenv('PASSWORD_STORE_GPG_OPTS')
        self._setenv('PASSWORD_STORE_X_SELECTION', 'X_SELECTION')
        self._setenv('PASSWORD_STORE_CLIP_TIME', 'CLIP_TIME')
        self._setenv('PASSWORD_STORE_UMASK')
        self._setenv('PASSWORD_STORE_GENERATED_LENGHT', 'GENERATED_LENGTH')
        self._setenv('PASSWORD_STORE_CHARACTER_SET', 'CHARACTER_SET')
        self._setenv('PASSWORD_STORE_CHARACTER_SET_NO_SYMBOLS',
                     'CHARACTER_SET_NO_SYMBOLS')
        self._setenv('PASSWORD_STORE_ENABLE_EXTENSIONS')
        self._setenv('PASSWORD_STORE_EXTENSIONS_DIR', 'EXTENSIONS')
        self._setenv('PASSWORD_STORE_SIGNING_KEY')
        self._setenv('GNUPGHOME')
        self.prefix = self.env['PASSWORD_STORE_DIR']

    def _setenv(self, var, env=None):
        """ Add var in the environnement variables directory.
            env must be an existing os environnement variables.
        """
        if env is None:
            env = var
        if env in os.environ:
            self.env[var] = os.environ[env]

    def _pass(self, arg=None, data=None):
        """ Call to password store """
        command = [self.passbinary]
        if arg is not None:
            command.extend(arg)

        process = Popen(command, universal_newlines=True, env=self.env,
                        stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr) = process.communicate(data)
        res = process.wait()
        if res:
            raise PasswordStoreError("%s: %s %s" % (list2cmdline(command),
                                     stdout, stderr))
        return stdout

    def insert(self, path, data, force=False):
        """ Multiline insertion into the password store. """
        arg = ['insert', '--multiline']
        if force:
            arg.append('--force')
        arg.append(path)
        return self._pass(arg, data)

class PasswordManager():

    def __init__(self, all):
        self.data = []
        self.all = all

    def get(self, password):
        """ Return the content of an entry in a password-store format. """
        entry = password.copy()
        string = ''
        if 'password' in entry:
            string = entry.pop('password', None) + '\n'
        entry.pop('path', None)
        for key, value in entry.items():
            string += "%s: %s\n" % (key, value)
        return string

    def satanize(self, clean):
        """ Clean parsed data in order to be imported to a store """
        for entry in self.data:
            # Remove the protocol prefix for the title
            entry['title'] = entry['title'].replace('https://', '')
            entry['title'] = entry['title'].replace('http://', '')

            # Make the title more command line friendly
            if clean:
                title = entry['title'].replace(" ", "_").replace("&", "and")
                title = title.replace('/', '-').replace('\\', '-')
                title = title.replace("@", "At").replace("'", "")
                entry['title'] = title.replace("[", "").replace("]", "")

            # Create path from title and group
            path = ''
            if 'group' in entry:
                path = entry.pop('group', None).replace('\\', '/')
            entry['path'] = os.path.join(path, entry.pop('title', None))

            # Remove the protocol prefix for the url
            if 'url' in entry:
                entry['url'] = entry['url'].replace('https://', '')
                entry['url'] = entry['url'].replace('http://', '')

            # Rough protection for fancy username/hostname like “; rm -Rf /\n”

            # Remove unused keys
            empty = [k for k, v in entry.items() if not v]
            for key in empty:
                entry.pop(key, None)

        # Detecting duplicate paths
        seen = []
        for entry in self.data:
            path = entry['path']
            if path in seen:
                while path in seen:
                    path += '0'
                seen.append(path)
                entry['path'] = path
            else:
                seen.append(path)

class PasswordManagerCSV(PasswordManager):
    def parse(self, file):
        reader = csv.DictReader(file, delimiter=',', quotechar='"')
        for row in reader:
            entry = OrderedDict()
            for key, csvkey in self.keys.items():
                if csvkey is not '':
                    entry[key] = row[csvkey]
                    row.pop(csvkey, None)

            if self.all:
                for col in row:
                    entry[col] = row[col]

            self.data.append(entry)

class Gorilla(PasswordManagerCSV):
    keys = {'title': 'title', 'password': 'password', 'login': 'user',
            'email': '', 'url': 'url', 'comments': 'notes',
            'group': 'group'}


class KeepassCSV(PasswordManagerCSV):
    keys = {'title': 'Account', 'password': 'Password', 'login': 'Login Name',
            'email': '', 'url': 'Web Site', 'comments': 'Comments',
            'group': ''}

class Lastpass(PasswordManagerCSV):
    keys = {'title': 'name', 'password': 'password', 'login': 'username',
            'email': '', 'url': 'url', 'comments': 'extra',
            'group': 'grouping'}

class PasswordExporter(PasswordManagerCSV):
    firstline = '# Generated by Password Exporter, Export format 1.1, Encrypted: undefined'
    keys = {'title': 'hostname', 'password': 'password', 'login': 'username',
            'email': '', 'url': '', 'comments': '',
            'group': ''}

    def parse(self, file):
        line = file.readline()
        if not line.startswith(self.firstline):
                die('Input format not supported')
        super(PasswordExporter, self).parse(file)

if __name__ == "__main__":
    # 'import.bash' did the sanity checks all these data are valid.
    try:
        manager = str(sys.argv[1])
        if manager not in importer_map:
            raise Exception()
        path = str(sys.argv[2])
        root = str(sys.argv[3])
        clean = bool(int(sys.argv[4]))
        force = bool(int(sys.argv[5]))
        extra = bool(int(sys.argv[6]))
    except Exception:
        die("This program should only be called by 'pass import'.")

    # Import and clean data
    ImporterClass = getattr(__import__('import'), importer_map[manager])
    importer = ImporterClass(extra)
    importer.parse(sys.stdin)
    importer.satanize(clean)

    # Insert data into the password store
    store = PasswordStore()
    for entry in importer.data:
        try:
            passpath = os.path.join(root, entry['path'])
            store.insert(passpath, importer.get(entry), force)
        except PasswordStoreError as e:
            die(e)

    # Success!
    success("Importing passwords from %s" % manager)
    if path is '':
        path = 'read from stdin'
    message("File: %s" % path)
    if root is not '':
        message("Root path: %s" % root)
    message("Number of password imported: %s" % len(importer.data))
    if clean:
        message("Imported data cleaned")
    if extra:
        message("Extra data conserved")
    message("Passwords imported:")
    for entry in importer.data:
        msg(entry['path'])
