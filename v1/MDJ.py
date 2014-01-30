#
# Mikes Daft Juukbox - Copyright (c) Michael Imelfort 2009 - 2012
#
# Description:
# Implements a jukebox interface for the XBMC. This will run like everyone wants a jukebox
# to run. It will also look like crap. Deal with it...
#
# This Program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This Program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with XBMC; see the file COPYING.  If not, write to
# the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# http://www.gnu.org/copyleft/gpl.html
#
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import re
import sys
import os
import random
import time
from threading import Thread

# plugin constants
__plugin__ = "script.MDJ"
__author__ = "minillinim"
__url__ = "https://github.com/minillinim/MDJ"
__version__ = "0.0.1"

#get actioncodes from keymap.xml
ACTION_PREVIOUS_MENU = 10

class MDJClass(xbmcgui.Window):
    #
    # Get ourselves a player
    #
    def __init__(self):

        # 
        # Some global variables
        #
        Addon = xbmcaddon.Addon( id=__plugin__)
        self.musicRoot = Addon.getSetting('music_root')    # point this at the root of your party music
        self.queueMax = int(Addon.getSetting('queue_max'))    # Max number of songs in the queue
        self.bgimg = os.path.join(Addon.getAddonInfo('path'),'images','skin.png')
        
        #
        # get and parse the global window dimensions
        #
        screenx = self.getWidth()
        screeny = self.getHeight()

        # set the global border
        globalBorder = 14

        # set the height of the top bar
        topBarHeight = 60

        # set the top and widths for the lists
        listTop = 105
        listWidth = (screenx - (3 * globalBorder)) / 2
        listHeight = screeny - listTop - globalBorder
        listLeftQueue = globalBorder
        listLeftSelector = 2 * globalBorder + listWidth

        #
        # Draw the skin
        #
        # add a background image
        self.backgroundImage = xbmcgui.ControlImage(0,0,screenx,screeny,self.bgimg)
        self.addControl(self.backgroundImage)

        # add the nowPlaying and queue count labels to the top of the screen
        self.nowPlayingFrame = xbmcgui.ControlLabel(listLeftQueue, 33, listWidth, topBarHeight, '', 'special12', '0xFFFFFFFF')
        self.addControl(self.nowPlayingFrame)
        self.nowPlayingFrame.setLabel('Welcome to Mike\'s daft juukbox... YTRB')

        self.qRemFrame = xbmcgui.ControlLabel(listLeftSelector , 33, listWidth, topBarHeight, '', 'special12', '0xFFFFFFFF')
        self.addControl(self.qRemFrame)
        self.qRemFrame.setLabel('Remaining: '+str(self.queueMax)+' songs.' )

        # add a list for the queued stuff
        self.queueList = xbmcgui.ControlList(listLeftQueue, listTop, listWidth, listHeight)
        self.addControl(self.queueList)

        # add a list of selections
        self.selectorList = xbmcgui.ControlList(listLeftSelector, listTop, listWidth, listHeight)
        self.addControl(self.selectorList)
        
        #
        # Set the state and path variables
        #
        self.userLock = 'unlocked'                      # The system starts in a state of being unlocked
        self.currentMode = 'choose_dir'                 # We need to choose the directory
        self.currentPlayingDirectory = ''               # The current playing directory
        self.nonePickedYet = True                       # check to see if at least one song has been picked...
        self.queueRemain = self.queueMax
        self.currentSong = ''
        self.playerRequired = True                      # do we need the player thread to keep going?
        self.playerActive = False                       # is the player thread still active

        #
        # For queue management
        #
        self.autoQueuedSongs = []                       # a list of all the enqueued songs
        self.userQueuedSongs = []                       # a list of all the user enqueued songs
        self.pretty2LongDict = {}                       # { prettyName : URL }
        self.long2PrettyDict = {}                       # { URL : prettyName }
        
        self.startJuukbox();
        
    #
    # Start actin like a juke box
    #
    def startJuukbox(self):
        # start by loading the directory listing
        self.getDirectory(self.musicRoot)

        # focus on the selector list
        self.setFocus(self.selectorList)

        # put the playlist manager on it's own thread
        self.managerThread = Thread(target=self.playlistManager, args=(2,))
        self.managerThread.start()

        # fix the queus window
        self.fixQueueWindow()

    #
    # process all inputs from the remote here we can override keymap.xml
    # and try do some other tricky stuff
    #
    # We won't try to catch the use of select on the selector list
    # we will handle that in it's own place
    #
    def onAction(self, action):
        if action == ACTION_PREVIOUS_MENU :
            self.quitMDJ()
            
    #
    # How to exit like a nice script
    #
    def quitMDJ(self):
        self.MDJalert("Waiting for player thread to exit...")
        self.playerRequired = False
        while(self.playerActive):
            time.sleep(0.5)
        self.close()
        
    #
    # When making selections
    #
    def onControl(self, control) :
        if control == self.selectorList :
            chosenItem = self.selectorList.getSelectedItem()
            if self.currentMode == 'choose_dir' :
                self.loadMusicList(chosenItem.getLabel())
                self.currentMode = 'musicLoaded'
            else :
                self.enqueueSong(chosenItem.getLabel())

    #
    # choose a directory to look into
    #
    def getDirectory(self, path) :
        list = os.listdir(path)
        for a in list :
            self.selectorList.addItem(a)

    #
    # get the contents of the directory and load it into the selectionlist
    #
    def loadMusicList(self, directory) :
        # clear the current list
        self.selectorList.reset()

        # get a list of all the songs...
        self.currentPlayingDirectory = os.path.join(self.musicRoot, directory)
        tmpList = os.listdir(self.currentPlayingDirectory)
        sortedSongList = []
        for fileName in tmpList :
            prettyName = self.prettyFyFile(fileName)
            longFileName = os.path.join(self.currentPlayingDirectory, fileName)
            self.pretty2LongDict[prettyName] = longFileName
            self.long2PrettyDict[longFileName] = prettyName
            sortedSongList.append(prettyName)
            self.autoQueuedSongs.append(longFileName)
        # sort the selection list
        sortedSongList.sort()
        for songTitle in sortedSongList :
            self.selectorList.addItem(songTitle)

    #
    # fix up files names to make them purdier...
    # sometimes we nuke it too much. so just return the
    # original
    #
    def prettyFyFile(self, fileName) :
        a = re.sub('^\d*\s', '', fileName)
        a = re.sub('^\d-\d\d\s', '', a)
        a = re.sub('\.m..$', '', a)
        a = re.sub('\.wma$', '', a)
        a = re.sub('^Track\s\d*', '', a)
        a = re.sub('\'', '', a)
        if a == '' :
            return fileName
        else :
            return a
    #
    # PlayList manager
    #
    def playlistManager(self, sleepyTime) :

        self.playerActive = True
        
        # wait for the user to catch up...
        while(self.nonePickedYet) :
            if(not self.playerRequired):
                self.playerActive = False
                break 
            time.sleep(0.5)
            
        if(not self.playerRequired):
            self.playerActive = False
            return
         
        # make the autoqueue list
        # shuffle the autoQueuedSongs
        random.seed(time.time())
        random.shuffle(self.autoQueuedSongs)        

        while(1) :
            if not xbmc.Player().isPlaying() :
                # check to see if the user queue is going...
                if not len(self.userQueuedSongs) == 0 :
                    # there are some songs on this list
                    songU = self.userQueuedSongs.pop(0)
                    self.currentSong = songU
                    xbmc.Player().play(songU)
                    # redraw the queued list of songs
                    self.nowPlaying()
                    self.qRemaining()
                    self.fixQueueWindow()
                else :
                    # get the guy off the top of the autolist
                    songA = self.autoQueuedSongs.pop(0)
                    # put this guy to the end of the auto list
                    self.autoQueuedSongs.append(songA)
                    self.currentSong = songA
                    xbmc.Player().play(songA)
                    # update the gui
                    self.nowPlaying()
                    
            # see if we've been asked to leave...
            if(not self.playerRequired):
                self.playerActive = False
                break 
            
        # make sure that the player is stopped before we leaver here...
        xbmc.Player().stop()
        self.MDJalert("Player stopped")
        time.sleep(3)

    #
    # Enqueue a song
    #
    def enqueueSong(self, prettyName) :
        # can't reenqueue the current song
        if(self.currentSong == self.pretty2LongDict[prettyName]):
            return 0
        
        # not allowed more than queueMax songs in the queue
        if(len(self.userQueuedSongs) >= self.queueMax) :
            return 0

        # not allowed to add a song to the queue twice
        for songU in self.userQueuedSongs :
            if songU == self.pretty2LongDict[prettyName] :
                return 0

        # ok we can add it to the queue
        self.userQueuedSongs.append(self.pretty2LongDict[prettyName])

        # move this guy to the end of the auto queue
        tmp = ''
        for songA in self.autoQueuedSongs :
            if songA == self.pretty2LongDict[prettyName] :
                tmp = songA
                self.autoQueuedSongs.remove(songA)
                break

        if not tmp == '' :
            self.autoQueuedSongs.append(tmp)
            
        # gui
        self.qRemaining()
        self.fixQueueWindow()
        self.nonePickedYet = False

    #
    # Now Playing
    #
    def nowPlaying(self) :
        self.nowPlayingFrame.setLabel('     Now playing:       ' + self.long2PrettyDict[self.currentSong])

    def qRemaining(self) :
        self.queueRemain = self.queueMax - len(self.userQueuedSongs)
        self.qRemFrame.setLabel('Remaining: ' + str(self.queueRemain) + ' songs.' )

    def fixQueueWindow(self) :
        self.queueList.reset()
        if not len(self.userQueuedSongs) == 0 :
            # there are some songs on this list
            for songTitle in self.userQueuedSongs :
                self.queueList.addItem(self.long2PrettyDict[songTitle])
        else :
            self.queueList.addItem('No songs in queue')

    def MDJalert(self, message) :
        self.nowPlayingFrame.setLabel(message)


mydisplay = MDJClass()
mydisplay.doModal()
del mydisplay