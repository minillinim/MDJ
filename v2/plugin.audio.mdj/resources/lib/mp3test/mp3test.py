#!/usr/bin/env python
###############################################################################
#
# __script_name__.py - description!
#
###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

__author__ = "Michael Imelfort"
__copyright__ = "Copyright 2012"
__credits__ = ["Michael Imelfort"]
__license__ = "GPL3"
__version__ = "0.0.1"
__maintainer__ = "Michael Imelfort"
__email__ = "mike@mikeimelfort.com"
__status__ = "Development"

###############################################################################

import argparse
import sys

import os
import re
#import errno

#import numpy as np
#np.seterr(all='raise')

#import matplotlib as mpl
#import matplotlib.pyplot as plt
#from mpl_toolkits.mplot3d import axes3d, Axes3D
#from pylab import plot,subplot,axis,stem,show,figure


###############################################################################
###############################################################################
###############################################################################
###############################################################################

from UserDict import UserDict
def stripnulls(data):
    "strip whitespace and nulls"
    return data.replace("\00", " ").strip()

class FileInfo(UserDict):
    "store file metadata"
    def __init__(self, filename=None):
        UserDict.__init__(self)
        self["name"] = filename

class MP3FileInfo(FileInfo):
    "store ID3v1.0 MP3 tags"
    tagDataMap = {"title"   : (  3,  33, stripnulls),
                  "artist"  : ( 33,  63, stripnulls),
                  "album"   : ( 63,  93, stripnulls),
                  "year"    : ( 93,  97, stripnulls),
                  "comment" : ( 97, 126, stripnulls),
                  "genre"   : (127, 128, ord)}

    def parse(self, filename):
        "parse ID3v1.0 tags from MP3 file"
        self.clear()
        try:
            fsock = open(filename, "rb", 0)
            try:
                fsock.seek(-128, 2)
                tagdata = fsock.read(128)
            finally:
                fsock.close()
            if tagdata[:3] == 'TAG':
                for tag, (start, end, parseFunc) in self.tagDataMap.items():
                    self[tag] = parseFunc(tagdata[start:end])
        except IOError:
            pass

    def __setitem__(self, key, item):
        if key == "name" and item:
            self.__parse(item)
        FileInfo.__setitem__(self, key, item)

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class MediaDir(object):
    """Functionality for recursively grepping info from media files"""
    goodExts = [".mp3", ".m4a", ".wma", ".ogg"]

    def __init__(self, path, parent=None):
        self.path = path
        self.parent = parent
        self.files = []             # list of files in this directory
        self.media_files = []       # list of confirmed media files
        self.subdirs = []           # list of sub drectories

        self.artist = "__UNKNOWN__"     # artist / band name
        self.album = "__UNKNOWN__"      # album name
        self.displayNames = {}      # song names, as would be displayed in a player


    def fullPath(self, F):
        return os.path.abspath(os.path.join(self.path, F))

    def loadDir(self):
        """recursively load this path and all subdirs"""
        items = os.listdir(self.path)
        for i in items:
            full_path = os.path.join(self.path, i)
            if os.path.isdir(full_path):
                D = MediaDir(full_path, parent=self)
                self.subdirs.append(D)
            elif os.path.isfile(full_path):
                if self.isMusic(i):
                    self.files.append(i)

        for D in self.subdirs:
            D.loadDir()

    def parseDir(self, hint = None, mungeOnFolder=False):
        """recursively parse the directory tree and try to
        work our artist, album and song names using id3 tags

        fail gracefully ... well try to...
        """
        if hint == None and mungeOnFolder == False:
            # primary call to this recursive function
            # try to work out stuff based on the tags
            artists_found = {}
            albums_found = {}
            for F in self.files:
                MP = {}
                if os.path.splitext(F)[1] == ".mp3":
                    MP = MP3FileInfo()
                    MP.parse(self.fullPath(F))

                # TODO: add wma, ogg etc...
                try:
                    self.displayNames[self.fullPath(F)] = MP['title']
                    if self.displayNames[self.fullPath(F)] == '':
                        raise KeyError

                    # try to work out artist and album entries
                    try:
                        artist = MP['artist'].upper()
                        if artist != '':
                            try:
                                artists_found[artist] += 1
                            except KeyError:
                                artists_found[artist] = 1
                    except KeyError: pass

                    try:
                        album = MP['album'].upper()
                        if album != '':
                            try:
                                albums_found[album] += 1
                            except KeyError:
                                albums_found[album] = 1
                    except KeyError: pass

                except KeyError:
                    # no tag information
                    self.displayNames[self.fullPath(F)] = self.mungeTitle(F)

            for D in self.subdirs:
                (artist, album) = D.parseDir()
                if artist != '':
                    artist = artist.upper()
                    try:
                        albums_found[album] += 1
                    except KeyError:
                        albums_found[album] = 1
                if album != '':
                    album = album.upper()
                    try:
                        artists_found[artist] += 1
                    except KeyError:
                        artists_found[artist] = 1

            most_common_artist = ["", -1]
            next_common_artist = ["", -1]
            most_common_album = ["", -1]
            next_common_album = ["", -1]

            # find the two most common artists for this folder
            for artist, count in artists_found.items():
                if artist != "__UNKNOWN__":
                    if count > most_common_artist[1]:
                        next_common_artist = [most_common_artist[0], most_common_artist[1]]
                        most_common_artist = [artist, count]
                    elif count == most_common_artist[1]:
                        next_common_artist = [artist, count]
            if most_common_artist[0] == "__UNKNOWN__" and next_common_artist[0] != "__UNKNOWN__":
                next_common_artist = most_common_artist

            if most_common_artist[1] > 0:
                # there must be a clear winner
                if most_common_artist[1] > 2 * next_common_artist[1]:
                    self.artist = most_common_artist[0]
                else:
                    self.artist = "__VARIOUS__"

            for album, count in albums_found.items():
                if album != "__UNKNOWN__":
                    if count > most_common_album[1]:
                        next_common_album = [most_common_album[0], most_common_album[1]]
                        most_common_album = [album, count]
                    elif count == most_common_album[1]:
                        next_common_album = [album, count]
            if most_common_album[0] == "__UNKNOWN__" and next_common_album[0] != "__UNKNOWN__":
                next_common_album = most_common_album

            if most_common_album[1] > 0:
                if most_common_album[1] > 2 * next_common_album[1]:
                    self.album = most_common_album[0]
                else:
                    self.album = "__VARIOUS__"

            if self.parent is None:
                # we are back at the top level, propagate down
                for D in self.subdirs:
                    D.parseDir(hint="__UNKNOWN__")

                # try make sense from folder names
                for D in self.subdirs:
                    D.parseDir(mungeOnFolder=True)

                # finally, try to propogate any gleaned namings downstream
                for D in self.subdirs:
                    D.parseDir(hint=self.artist)

            else:
                return (self.artist, self.album)
        elif mungeOnFolder == False:
            # we are somewhere in the second propagation
            if self.artist == "__UNKNOWN__" and hint is not None and hint != "__UNKNOWN__":
                self.artist = hint
            for D in self.subdirs:
                D.parseDir(hint=self.artist)
        else: # mungeOnFolder == True
            if len(self.subdirs) == 0:
                # bottom level -> try to work out album name
                if self.album == "__UNKNOWN__":
                    self.album = self.mungeAlbum()
            else:
                # perhaps we are in a directory at the band level
                # either way, it's time to munge on the artist name
                if self.artist == "__UNKNOWN__":
                    self.artist = self.mungeArtist()

                for D in self.subdirs:
                    D.parseDir(mungeOnFolder=True)

    def isMusic(self, file):
        return os.path.splitext(file)[1] in self.goodExts

    def mungeArtist(self):
        return os.path.split(self.path)[1].upper()

    def mungeAlbum(self):
        return os.path.split(self.path)[1].upper()

    def mungeTitle(self, file):
        return re.sub( "^[ ]*-[ ]*", "",re.sub("^\d+ ", "", os.path.splitext(file)[0]))

    def extract(self, fid=1):
        """extract all the gleaned info from the directory"""
        ret = []
        for F in self.files:
            ret.append((fid, self.artist.title(), self.album.title(), self.displayNames[self.fullPath(F)], self.fullPath(F)))
            fid += 1
        for D in self.subdirs:
            (fid, tmp) = D.extract(fid=fid)
            ret += tmp
        return (fid, ret)

    def __str__(self):
        _str = ""
        for F in self.files:
            #_str += "%s\n" % self.fullPath(F)
            _str += "%s :: %s :: %s\n" % (self.artist.title(), self.album.title(), self.displayNames[self.fullPath(F)])
        for D in self.subdirs:
            _str += str(D)

        return _str

###############################################################################
###############################################################################
###############################################################################
###############################################################################


def doWork( args ):
    """ Main wrapper"""

    MD = MediaDir(args.folder)
    MD.loadDir()
    MD.parseDir()
    print MD.extract()
    """
    MP =     MP3FileInfo()
    MP.parse(args.mp3)
    MP.tagDataMap
    print MP['title']
    """
    return 0

###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('folder', help="root mp3 folder")
    #parser.add_argument('positional_arg2', type=int, help="Integer argument")
    #parser.add_argument('positional_arg3', nargs='+', help="Multiple values")
    #parser.add_argument('-X', '--optional_X', action="store_true", default=False, help="flag")

    # parse the arguments
    args = parser.parse_args()

    # do what we came here to do
    doWork(args)

###############################################################################
###############################################################################
###############################################################################
###############################################################################


