#!/usr/bin/env python
###############################################################################
#                                                                             #
#    mdj.py - jukebox plugin for XBMC - third time's a charm!                 #
#                                                                             #
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

import sys
import xbmc
import xbmcgui
import xbmcplugin
import os
import xbmcaddon
import re
import random
import time
from threading import Thread, Lock
from UserDict import UserDict
import urllib
import urlparse
import Image

# point at the local python modules
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0], "resources","lib","mp3test"))
from mp3test import MediaDir

###############################################################################

__plugin__      = "plugin.audio.mdj"
__addon__       = xbmcaddon.Addon(id=__plugin__)
__author__      = "Michael Imelfort"
__copyright__   = "Copyright 2012"
__credits__     = ["Michael Imelfort"]
__license__     = "GPL3"
__version__     = "0.0.1"
__maintainer__  = "Michael Imelfort"
__url__         = "https://github.com/minillinim/MDJ"
__email__       = "mike@mikeimelfort.com"
__status__      = "Development"

###############################################################################

action_unknown = 0 #'y', black
action_move_left = 1 #dpad left
action_move_right = 2 #dpad right
action_move_up = 3 #dpad up
action_move_down = 4 #dpad down
action_skip_next = 5 #left trigger
action_skip_previous = 6 #right trigger
action_select = 7 #'a'
action_back = 9 #'b'
action_menu = 10 #'back'
action_info = 11 #'info' (the white button)
action_stop = 13 #'start'
action_display = 18 #'x'

###############################################################################

def alert(title, message="", time=5000):
    """nicer than the XBMC way to do it"""
    xbmc.executebuiltin('Notification(%s,%s,%d)' % (title, message, time))

def build_url(query):
    return base_url + '?' + urllib.urlencode(query)

print sys.argv
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = urlparse.parse_qs(sys.argv[2][1:])
imageDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images') # where we keep images

###############################################################################

# for the MP3-based code
#_author__ = "Mark Pilgrim (mark@diveintopython.org)"
#_version__ = "$Revision: 1.3 $"
#_date__ = "$Date: 2004/05/05 21:57:19 $"
#_copyright__ = "Copyright (c) 2001 Mark Pilgrim"
#_license__ = "Python"

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class Juukbox(xbmcgui.Window):
    """Handle all the nitty gritties about the skin and the way it looks"""
    def __init__(self, mode="juukbox"):
        """Basic setup, window is a MDJ (xbmc.Window)"""
        self.backgroundImage = None
        self.scaleX = 0.
        self.scaleY = 0.
        self.screenX = 0.
        self.screenY = 0.
        self.mode = mode

        #------------------------------------------------------
        # If called in "settings" mode -> adjust these settings in settings.xml and quit
        if self.mode == "settings":
            __addon__.openSettings()
            sys.exit()

        #------------------------------------------------------
        # If called in "testRes" mode -> show the user the resolution adjustment background image
        elif self.mode == "resTest":
            self.fudgeResolution()
            self.renderTestSKin()

        #------------------------------------------------------
        # Otherwise, we're a juukbox
        else:
            self.musicRoot = __addon__.getSetting('music_root')                        # where the music is at bra!
            self.queueMax = int(float(__addon__.getSetting('queue_max')))              # max number of items in the queue
            self.userEmbargo = int(float(__addon__.getSetting('user_embargo')))* 60    # number of seconds that must be waited until we can replay an item (user-selected)
            self.autoEmbargo = int(float(__addon__.getSetting('auto_embargo')))* 60    # number of seconds that must be waited until we can replay an item (autoqueued)
            self.pageSize = int(float(__addon__.getSetting('page_size')))              # page up / down size

            # handle the nitty gritty of lists and queues
            self.SM = SongManager(self.musicRoot,
                                  self.queueMax,
                                  self.userEmbargo,
                                  self.autoEmbargo,
                                  self.pageSize)

            # We need to know when to kill threads and quit
            self.playerLock = Lock()            # the next two variables need to be made thread safe
            self.playerRequired = True          # do we need the player thread to keep going?
            self.playerActive = False           # is the player thread still active

            #------------------------------------------------------
            # skin related stuff
            self.topBand = None                 # band that runs across the top where "now playing" is located
            self.cornerImg = None               # image displayed in the top right corner which holds the number remaining
            self.remainingImg = None            # an image of a number showing how many remain to be added to the queue
            self.nowImg = None                  # an image which says "Now Playing"
            self.selectGhost = None             # opaque background for the select list
            self.queueGhost = None              # opaque background for the queue list
            self.backgroundTiles = []           # Images to be tiled on the background
            self.tilingPattern = [1,1]          # how many tiles to add to the background (X x Y)
            self.queueList = None
            self.selectorList = None
            self.nowPlayingFrame = None

            # kill these
            self.qRemFrame = None
            self.backgroundImage = None

            # now set up all the parts
            self.initialiseJuukbox()
    #------------------------------------------------------
    # resolution crud
    #
    def fudgeResolution(self):
        """Get the fudge factor and adjust the x/y coords"""
        self.scaleX = 1. + float(__addon__.getSetting('w_fudge'))/1000.
        self.scaleY = 1. + float(__addon__.getSetting('h_fudge'))/1000.
        self.screenX = int(self.getWidth() / self.scaleX)
        self.screenY = int(self.getHeight() / self.scaleY)

    def renderTestSKin(self):
        """Render the resolution test skin"""
        self.backgroundImage = xbmcgui.ControlImage(0,
                                                    0,
                                                    self.screenX,
                                                    self.screenY,
                                                    os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('rt_bg_img')),
                                                    aspectRatio=0)

        self.addControl(self.backgroundImage)

    #------------------------------------------------------
    # jukebox functionality
    #
    def initialiseJuukbox(self):
        """load the music and draw the skin for the first time"""
        self.createSkin()
        self.SM.loadMusicList()
        # Draw the skin for the first time
        self.reRender()
        self.alert('Welcome to Mike\'s daft juukbox... YTRB')
        self.startJuukbox()

    def createSkin(self):
        """make all the list boxes, etc...

        Edit here to "skin" the juukbox
        """
        self.fudgeResolution()

        v_border = 30                # fixed border for all rendered objects ( vertical )
        h_border = 14                # fixed border for all rendered objects ( horizontal )
        top_bar_height = 60        # the height of the top bar
        list_width = int((self.screenX - (3. * h_border)) / 2.)
        list_height = int(self.screenY - top_bar_height - (3. * v_border))
        list_top = int((2. * v_border) + top_bar_height)

        list_left_queue = h_border
        list_left_selector = int((2. * h_border) + list_width)

        # add a background image
        self.backgroundImage = xbmcgui.ControlImage(0,
                                                    0,
                                                    self.screenX,
                                                    self.screenY,
                                                    os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('df_bg_img')),
                                                    aspectRatio=0)

        # add the nowPlaying and queue count frames to the top of the screen
        self.nowPlayingFrame = xbmcgui.ControlLabel(list_left_queue,
                                                    v_border,
                                                    list_width,
                                                    top_bar_height,
                                                    '',
                                                    'special12',
                                                    '0xFFFFFFFF',
                                                    )
        self.qRemFrame = xbmcgui.ControlLabel(list_left_selector,
                                              v_border,
                                              list_width,
                                              top_bar_height,
                                              '',
                                              'special12',
                                              '0xFFFFFFFF'
                                              )
        # add a list for the queued stuff
        self.queueList = xbmcgui.ControlList(list_left_queue,
                                             list_top,
                                             list_width,
                                             list_height,
                                             selectedColor='0x1234FFFF'
                                             )
        # add a list of selections
        self.selectorList = xbmcgui.ControlList(list_left_selector,
                                                list_top,
                                                list_width,
                                                list_height,
                                                buttonFocusTexture=os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('df_bf_img')),
                                                font='special16',
                                                )
        # anchor these guys to the window
        self.addControl(self.backgroundImage)
        self.addControl(self.nowPlayingFrame)
        self.addControl(self.qRemFrame)
        self.addControl(self.queueList)
        self.addControl(self.selectorList)

    def startJuukbox(self):
        """let's get this show on the road"""
        # put the playlist manager on it's own thread
        self.managerThread = Thread(target=self.managePlaylist)
        self.managerThread.start()
        self.reRender()
        self.centerSelectorAt()

    def stopJuukbox(self):
        """exit like a nice script"""
        self.alert("Sending player kill signal")
        self.playerLock.acquire()
        self.playerRequired = False
        self.playerLock.release()

        self.alert("Waiting for player thread to exit...")
        while(1):
            with self.playerLock:
                if not self.playerActive:
                    break
            time.sleep(2)

        del self.nowPlayingFrame
        del self.qRemFrame
        del self.queueList
        del self.selectorList

        self.close()

    def onAction(self, action):
        """process all inputs from the remote here

        use overrides in \ keymap.xml and try do some other tricky stuff
        We won't try to catch the use of select on the selector list
        we will handle that in it's own place"""

        #print "ACT: %d" % action.getId()

        if self.mode == 'resTest':
            if action.getId() == 92:
                self.close()

        elif self.mode == 'juukbox':
            if action.getId() == 92:
                self.stopJuukbox()

            # skip alpha
            elif action.getId() == 58:
                self.centerSelectorAt(self.SM.getNextAlphaPos(self.selectorList.getSelectedPosition(), direction='reverse'))
            elif action.getId() == 59:
                self.centerSelectorAt(self.SM.getNextAlphaPos(self.selectorList.getSelectedPosition(), direction='forward'))

            # skip artist
            elif action.getId() == 60:
                self.centerSelectorAt(self.SM.getNextArtistPos(self.selectorList.getSelectedPosition(), direction='reverse', page=True))
            elif action.getId() == 61:
                self.centerSelectorAt(self.SM.getNextArtistPos(self.selectorList.getSelectedPosition(), direction='reverse'))
            elif action.getId() == 62:
                self.centerSelectorAt(self.SM.getNextArtistPos(self.selectorList.getSelectedPosition(), direction='forward'))
            elif action.getId() == 63:
                self.centerSelectorAt(self.SM.getNextArtistPos(self.selectorList.getSelectedPosition(), direction='forward', page=True))

            # skip album
            elif action.getId() == 64:
                self.centerSelectorAt(self.SM.getNextAlbumPos(self.selectorList.getSelectedPosition(), direction='reverse', page=True))
            elif action.getId() == 65:
                self.centerSelectorAt(self.SM.getNextAlbumPos(self.selectorList.getSelectedPosition(), direction='reverse'))
            elif action.getId() == 66:
                self.centerSelectorAt(self.SM.getNextAlbumPos(self.selectorList.getSelectedPosition(), direction='forward'))
            elif action.getId() == 67:
                self.centerSelectorAt(self.SM.getNextAlbumPos(self.selectorList.getSelectedPosition(), direction='forward', page=True))

    def onControl(self, control):
        """When making selections"""
        if self.mode == 'juukbox':
            if control == self.selectorList:
                # someone clicked a song
                pos = self.selectorList.getSelectedPosition()
                if self.SM.enqueueSong(pos):
                    with self.playerLock:
                        self.playerActive = True
                    time.sleep(0.5)
                    self.reRender()
                    self.centerSelectorAt(pos-1)

    def managePlaylist(self):
        """play the next item!"""
        keep_going = True
        sleep_time = 2
        while keep_going:
            # see if we've been asked to leave...
            with self.playerLock:
                if self.playerActive: # wait for the user to catch up...
                    if not self.playerRequired:
                        self.playerActive = False
                        keep_going = False

                    # make sure music is playing and if not, play some
                    if not xbmc.Player().isPlaying():
                        (song_url, song_title) = self.SM.getNextItem()
                        xbmc.Player().play(song_url)
                        # redraw the queued list of items
                        self.renderNowPlaying(song_title)
                        self.renderQueueWindow()
                        self.renderQRemaining()

            if keep_going:
                time.sleep(2)

        # make sure that the player is stopped before we leave here...
        xbmc.Player().stop()
        self.alert("Player stopped")

    #------------------------------------------------------
    # IO and rendering
    #
    def renderNowPlaying(self, itemName):
        """update the now playing area"""
        self.nowPlayingFrame.setLabel('     Now playing:       %s' % itemName)

    def alert(self, message):
        """write free text to the 'now playing' area"""
        self.nowPlayingFrame.setLabel(message)

    def renderQRemaining(self):
        """update the queue remaining area"""
        self.qRemFrame.setLabel('Remaining: %d songs' % self.SM.queueRemain)

    def renderQueueWindow(self):
        """write the current list of enqueued items"""
        self.queueList.reset()
        userQ = self.SM.getEnqueued()
        if len(userQ) == 0:
            self.queueList.addItem('No songs in queue')
        else:
            # there are some items on this list
            for display_name in userQ:
                self.queueList.addItem(display_name)

    def renderSelectionWindow(self):
        """write the list of select-able items"""
        self.selectorList.reset()
        # sort the names and add to the selection list
        for display_name in self.SM.getAvailable():
            self.selectorList.addItem(display_name)

    def getNumDisplayed(self):
        """Work out how many items are displayed in the select list"""
        return int(float(self.selectorList.getHeight() + self.selectorList.getSpace()) /
                   float(self.selectorList.getSpace() + self.selectorList.getItemHeight())
                   )-1

    def getFocusPos(self, pos):
        """Center the focus on screen"""
        num_disp = self.getNumDisplayed()
        jump_2_middle = int(num_disp/2)
        if pos <= jump_2_middle:
            return pos
        elif pos+jump_2_middle >= self.selectorList.size():
            return self.selectorList.size()-1
        else:
            return pos + jump_2_middle

    def centerSelectorAt(self, pos=0):
        """Take care of centering the selector at a given position"""
        if pos <= 0:
            pos = 3
        if pos >= self.selectorList.size():
            pos = self.selectorList.size()-1
        self.selectorList.selectItem(self.getFocusPos(pos))
        self.selectorList.selectItem(pos)

    def reRender(self):
        """Re-render the screen"""
        self.renderSelectionWindow()
        self.renderQueueWindow()
        self.renderQRemaining()
        self.setFocus(self.selectorList)

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class SongManager(object):
    """The main window for implementing the jukebox interface"""
    def __init__(self,
                 musicRoot,
                 queueMax,
                 userEmbargo,
                 autoEmbargo,
                 pageSize):

        # take care of the passed variables
        self.musicRoot = musicRoot
        self.queueMax = queueMax
        self.embargoDelay = {'user' : userEmbargo, 'auto':  autoEmbargo}
        self.pageSize = pageSize

        # Set the state and path variables
        self.userLock = 'unlocked'          # The system starts in a state of being unlocked
        self.nonePickedYet = True           # check to see if at least one item has been picked...
        self.queueRemain = self.queueMax
        self.currentSong = ''

        self.SMLock = Lock()                # play lists get accessed concurrently

        self.ST = SongTree()                # structure for storing the songs

        # For queue management
        # len(autoQ) + len(userQ) == constant, intersection(autoQ, userQ) == None
        self.autoQ = []                     # a list of all the loaded items ( by index )
        self.userQ = []                     # a list of all the user enqueued items ( by index )
        self.fid2info = {}                  # index -> information
        self.itemLastPlayed = {}            # Take note of when items were last played { fid -> ( type, time ) }

        self.position2Fid = {}              # position in the selection list -> fid
        self.position2Type = {}             # same but to type

        self.positionAlpha = []            # [pos, pos, ...] of all the alphabets
        self.positionArtist = []
        self.positionAlbum = []

    def loadMusicList(self):
        """get the contents of a media directory and load it into the autoQ"""
        # get a list of all the items...
        MD = MediaDir(self.musicRoot)
        MD.loadDir()
        MD.parseDir()
        (num_items, musics) = MD.extract()

        with self.SMLock:
            for (fid, artist, album, title, full_path) in musics:
                self.ST.addSong(artist, album, title, fid)
                # have something to add!
                self.fid2info[fid] = (artist, album, title, full_path)
                self.autoQ.append(fid)

            # shuffle the autoQ
            random.seed(time.time())
            random.shuffle(self.autoQ)

    def enqueueSong(self, position):
        """enqueue an item"""
        # only so many items in a queue
        with self.SMLock:
            if(len(self.userQ) >= self.queueMax):
                return False

            type = self.position2Type[position]
            if type != 'title':
                return False

            fid = self.position2Fid[position]

            # do all the checking in this call
            if not self.isEmbargoed(fid):
                self.userQ.append(fid)
                self.itemLastPlayed[fid] = ('user', time.time())

            # move this guy to the end of the auto queue
            self.autoQ.remove(fid)
            self.autoQ.append(fid)

            # fix the number remaining
            self.queueRemain = self.queueMax-len(self.userQ)

            # we're off
            self.nonePickedYet = False
        return True

    def getAvailable(self):
        """work out which items we are able to give as selection options"""
        ret_list = []
        # clear these guys
        self.positionAlpha = []            # [pos, pos, ...] of all the alphabets
        self.positionArtist = []
        self.positionAlbum = []
        self.position2Fid = {}
        self.position2Type = {}

        pos = 0
        curr_time = time.time()
        for (type, fid, text) in self.ST.getDisplay():
            if type == 'title':
                if not self.isEmbargoed(fid, currTime=curr_time):
                    ret_list.append(text)
                    self.position2Fid[pos] = fid
                    self.position2Type[pos] = type
                    pos += 1
            else:
                # set these guys up for quick navigation
                if type == 'alpha':
                    self.positionAlpha.append(pos)
                if type == 'artist':
                    self.positionArtist.append(pos)
                if type == 'album':
                    self.positionAlbum.append(pos)

                ret_list.append(text)
                self.position2Type[pos] = type
                pos += 1

        return ret_list

    def getNextAlphaPos(self, pos, direction='forward'):
        """Return the position of the next alphabet sep"""
        length = len(self.positionAlpha)
        r = range(length)
        if direction == 'forward':
            for i in r:
                if self.positionAlpha[i] >= pos:
                    if i + 1 < length:
                        return self.positionAlpha[i + 1]
                    else:
                        return self.positionAlpha[0]
            return self.positionAlpha[0]
        else:
            r.reverse()
            for i in r:
                if self.positionAlpha[i] <= pos:
                    if i - 1 >= 0:
                        return self.positionAlpha[i - 1]
                    else:
                        return self.positionAlpha[length-1]
            return self.positionAlpha[length-1]

    def getNextArtistPos(self, pos, page=False, direction='forward'):
        """Return the position of the next album sep"""
        length = len(self.positionArtist)
        r = range(length)
        if direction == 'forward':
            for i in r:
                if self.positionArtist[i] >= pos:
                    if page:
                        goto = i + self.pageSize
                    else:
                        goto = i + 1
                    if goto < length:
                        return self.positionArtist[goto]
                    else:
                        return self.positionArtist[0]
            return self.positionArtist[0]
        else:
            r.reverse()
            for i in r:
                if self.positionArtist[i] <= pos:
                    if page:
                        goto = i - self.pageSize
                    else:
                        goto = i - 1
                    if goto >= 0:
                        return self.positionArtist[goto]
                    else:
                        return self.positionArtist[length-1]
            return self.positionArtist[length-1]

    def getNextAlbumPos(self, pos, page=False, direction='forward'):
        """Return the position of the next artist sep"""
        length = len(self.positionAlbum)
        r = range(length)
        if direction == 'forward':
            for i in r:
                if self.positionAlbum[i] >= pos:
                    if page:
                        goto = i + self.pageSize
                    else:
                        goto = i + 1
                    if goto < length:
                        return self.positionAlbum[goto]
                    else:
                        return self.positionAlbum[0]
            return self.positionAlbum[0]
        else:
            r.reverse()
            for i in r:
                if self.positionAlbum[i] <= pos:
                    if page:
                        goto = i - self.pageSize
                    else:
                        goto = i - 1
                    if goto >= 0:
                        return self.positionAlbum[goto]
                    else:
                        return self.positionAlbum[length-1]
            return self.positionAlbum[length-1]

    def getEnqueued(self):
        """get the list of currently enqueued items"""
        with self.SMLock:
            return [self.getDisplayName(fid) for fid in self.userQ]

    def getNextItem(self):
        """get the next item to play"""
        # Only called from within a block with a lock. So no need to lock again
        # first, check the userQ
        fid = None
        with self.SMLock:
            if not len(self.userQ) == 0:
                # there are some items on this list
                fid = self.userQ.pop(0)
            else:
                # get the guy off the top of the autolist
                # note that we ignore any embargo, the show must go on!!!
                fid = self.autoQ.pop(0)
                # put this guy to the end of the auto list
                self.autoQ.append(fid)
        return self.getDisplayName(fid, getURL=True)

    def isEmbargoed(self, fid, currTime=0):
        """check to see if there is any reason to make this item unavailable"""
        if currTime == 0:
            currTime = time.time()
        try:
            # see if this guy is embargoed
            (type, last_time) = self.itemLastPlayed[fid]
            since = currTime - last_time
            embargo_limit = self.embargoDelay[type]
            if since > embargo_limit:
                # remove from the list
                del(self.itemLastPlayed[fid])
                return False
            else:
                return True
        except KeyError:
            # no problem
            return False

    def reviewEmbargoed(self):
        """check to see if any unavailable songs can be re-enlisted"""
        curr_time = time.time()
        to_remove = []
        for fid, (type, last_time) in self.itemLastPlayed.items():
            since = curr_time - last_time
            embargo_limit = self.embargoDelay[type]
            if since > embargo_limit:
                to_remove.append(fid)
        for fid in to_remove:
            # remove from the list
            del(self.itemLastPlayed[fid])
        return len(to_remove)

    def getDisplayName(self, fid, getURL=False):
        """return a descriptive string for the media item"""
        (artist, album, title, full_path) = self.fid2info[fid]
        if getURL:
            return (full_path, "%s - %s" % (artist, title))
        return "%s - %s" % (artist, title)

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class SongTree(object):
    """Object for storing songs that makes updating lists and searching more efficient"""
    def __init__(self):
        self.alphas = ['#'] + [chr(i) for i in range(65,91)]
        self.alphaHash = {}
        for let in self.alphas:
            self.alphaHash[let] = {}

    def addSong(self, artist, album, title, fid):
        let = artist[0]
        try:
            alpha_hash = self.alphaHash[let]
        except KeyError:
            alpha_hash = self.alphaHash['#']

        try:
            artist_hash = alpha_hash[artist]
            try:
                artist_hash[album][title] = fid
            except KeyError:
                artist_hash[album] = { title : fid }
        except KeyError:
            alpha_hash[artist] = { album : { title : fid } }  # add the whole thing in one go

    def getDisplay(self):
        """get display names for the songs + separators

        This is a generator function:
        yields: (type, fid, display) where type is from:
            None, 'alpha', 'artist', 'album' and 'title'
        """

        title = (None, None, "No songs available")
        ret_alpha_sep = True
        alpha_index = 0
        alpha = self.alphas[alpha_index]
        done = False
        ret_artist_sep = True
        next_artist_found = False

        # buffer the first alpha
        while not next_artist_found:
            alpha_index += 1
            try:
                alpha = self.alphas[alpha_index]
                if len(self.alphaHash[alpha].keys()) > 0:
                    next_artist_found = True
            except IndexError:
                # end of the line!
                done = True
                break

        if not done:
            # buffer the first artist, album, title
            artist_index = 0
            artist_list = sorted(self.alphaHash[alpha].keys())
            artist = artist_list[artist_index]

            ret_album_sep = True
            album_list = sorted(self.alphaHash[alpha][artist].keys())
            album_index = 0
            album = album_list[album_index]

            title_list = sorted(self.alphaHash[alpha][artist][album].keys())
            title_index = 0

            while not done:
                # see if we should yield separators
                if ret_alpha_sep:
                    ret_alpha_sep = False
                    yield ('alpha', None, alpha)
                if ret_artist_sep:
                    ret_artist_sep = False
                    yield ('artist', None, "     %s" % artist)
                if ret_album_sep:
                    ret_album_sep = False
                    yield ('album', None, "          %s" % album)

                # we will yield a song title
                title = title_list[title_index]
                fid = self.alphaHash[alpha][artist][album][title]
                title_index += 1
                if title_index == len(title_list):
                    # end of the songs for this album
                    title_index = 0
                    ret_album_sep = True
                    album_index += 1
                    try:
                        album = album_list[album_index]
                    except IndexError:
                        # that was the last album for this artist
                        album_index = 0
                        ret_artist_sep = True
                        artist_index += 1
                        try:
                            artist = artist_list[artist_index]
                        except IndexError:
                            # that was the last artist starting with that letter
                            artist_index = 0
                            ret_alpha_sep = True
                            # find the next available artist
                            next_artist_found = False
                            while not next_artist_found:
                                alpha_index += 1
                                try:
                                    alpha = self.alphas[alpha_index]
                                    if len(self.alphaHash[alpha].keys()) > 0:
                                        next_artist_found = True
                                except IndexError:
                                    # end of the line!
                                    done = True
                                    break
                            if not done:
                                artist_list = sorted(self.alphaHash[alpha].keys())
                                artist = artist_list[artist_index]
                            else:
                                break
                        album_list = sorted(self.alphaHash[alpha][artist].keys())
                        album = album_list[album_index]
                    title_list = sorted(self.alphaHash[alpha][artist][album].keys())

                yield ('title', fid, "               %s" % title)
        yield ('title', fid, "               %s" % title)

###############################################################################
###############################################################################
###############################################################################
###############################################################################

mode = args.get('mode', None)
print mode
if mode is None:
    # this is the pre-juukbox window which allows you to edit settings etc...

    # normal mode
    url = build_url({'mode': 'juukbox'})
    li = xbmcgui.ListItem('Start Juukbox',
                          iconImage=os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('play_img')))
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)

    # settings mode
    url = build_url({'mode': 'settings'})
    li = xbmcgui.ListItem('Edit Settings',
                          iconImage=os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('cog_img')))
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)

    # resolution mode
    url = build_url({'mode': 'resTest'})
    li = xbmcgui.ListItem('Adjust Resolution',
                          iconImage=os.path.join(os.path.dirname(os.path.realpath(__file__)), __addon__.getSetting('res_img')))
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)


    xbmc.executebuiltin('Container.SetViewMode(%d)' % 500)
    xbmcplugin.endOfDirectory(addon_handle)

else:
    # Run the juukbox
    juukbox = Juukbox(mode=mode[0])
    juukbox.doModal()
    try:
        del juukbox
    except:
        pass

###############################################################################
###############################################################################
###############################################################################
###############################################################################
