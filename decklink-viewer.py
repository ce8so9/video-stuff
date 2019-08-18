#!/usr/bin/env python3

# Simple script to show video and play audio from decklink capture cards

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

import os, sys
import time

Gst.init(None)
Gst.init_check(None)

TITLE = "DeckLink Viewer"

class PlayerWidget(Gtk.Box):
    """ This is the gtksink widget """
    def __init__(self, connection, videoformat, mode):
        super().__init__()
        print("Creating new pipeline (%s, %s, %s)" % (connection, videoformat, mode))
        self.pipeline = Gst.Pipeline()
        self.decklink = Gst.ElementFactory.make("decklinkvideosrc")
        self.decklink.set_property("device-number", 0)
        self.decklink.set_property("connection", connection)
        self.decklink.set_property("video-format", videoformat)
        self.decklink.set_property("mode", mode)
        self.decklinksnd = Gst.ElementFactory.make("decklinkaudiosrc")
        self.decklinksnd.set_property("do-timestamp", True)
        self.decklinksnd.set_property("alignment-threshold", 100)
        self.connect('realize', self.on_realize)

    def on_realize(self, widget):
        playerFactory = self.decklink.get_factory()
        videoconvert = playerFactory.make('videoconvert')
        gtksink = playerFactory.make('gtksink')
        audioconvert = playerFactory.make('audioconvert')
        pulsesink = playerFactory.make('pulsesink')
        pulsesink.set_property('sync', False)
        self.pipeline.add(self.decklink)
        self.pipeline.add(videoconvert)
        self.pipeline.add(gtksink)
        self.pipeline.add(self.decklinksnd)
        self.pipeline.add(audioconvert)
        self.pipeline.add(pulsesink)
        self.decklink.link(videoconvert)
        self.decklinksnd.link(audioconvert)
        videoconvert.link(gtksink)
        audioconvert.link(pulsesink)

        self.pack_start(gtksink.props.widget, True, True, 0)
        gtksink.props.widget.show()
        self.pipeline.set_state(Gst.State.PLAYING)

class MainWindow(Gtk.Window):
    def get_modes(self):
        decklink = Gst.ElementFactory.make("decklinkvideosrc")
        modes = []
        for mode in dict(decklink.get_property("mode").__enum_values__).values():
            modes.append(mode.value_name)
        return modes

    def get_connections(self):
        decklink = Gst.ElementFactory.make("decklinkvideosrc")
        connections = []
        for connection in dict(decklink.get_property("connection").__enum_values__).values():
            connections.append(connection.value_name)
        return connections

    def get_videoformats(self):
        decklink = Gst.ElementFactory.make("decklinkvideosrc")
        videoformats = []
        for videoformat in dict(decklink.get_property("video-format").__enum_values__).values():
            videoformats.append(videoformat.value_nick)
        return videoformats

    def __init__(self):
        Gtk.Window.__init__(self, title=TITLE)
        self.fullscreened = False
        self.set_default_size(1920, 1080)

        self.grid = Gtk.Grid()
        self.add(self.grid)
        self.grid.show()

        self.modes, self.connections, self.videoformats = self.get_modes(), self.get_connections(), self.get_videoformats()
        self.mode, self.videoformat, self.connection = 'HD1080 60p', "10bit-rgb", "HDMI"

        cell = Gtk.CellRendererText()

        modelist = Gtk.ListStore(str)
        for val in self.modes:
            modelist.append([val])
        self.modebox = Gtk.ComboBox(model=modelist)
        self.grid.attach(self.modebox, 0, 1, 1, 1)
        self.modebox.pack_start(cell, False)
        self.modebox.add_attribute(cell, "text", 0)
        self.modebox.set_active(self.modes.index(self.mode))
        self.modebox.show()
        self.modebox.connect("changed", self.on_changed_setting)

        videoformatlist = Gtk.ListStore(str)
        for val in self.videoformats:
            videoformatlist.append([val])
        self.videoformatbox = Gtk.ComboBox(model=videoformatlist)
        self.grid.attach(self.videoformatbox, 1, 1, 1, 1)
        self.videoformatbox.pack_start(cell, False)
        self.videoformatbox.add_attribute(cell, "text", 0)
        self.videoformatbox.set_active(self.videoformats.index(self.videoformat))
        self.videoformatbox.show()
        self.videoformatbox.connect("changed", self.on_changed_setting)

        connectionlist = Gtk.ListStore(str)
        for val in self.connections:
            connectionlist.append([val])
        self.connectionbox = Gtk.ComboBox(model=connectionlist)
        self.grid.attach(self.connectionbox, 2, 1, 1, 1)
        self.connectionbox.pack_start(cell, False)
        self.connectionbox.add_attribute(cell, "text", 0)
        self.connectionbox.set_active(self.connections.index(self.connection))
        self.connectionbox.show()
        self.connectionbox.connect("changed", self.on_changed_setting)

        self.playerWidget = None
        self.load_playerwidget()

        self.connect("key-press-event", self.on_key_press)
        self.connect("key-release-event", self.on_key_release)
        self.lostsignal = False
        self.timer = GLib.timeout_add(100, self.on_timer, self)

    def on_changed_setting(self, combo):
        self.mode = self.modes[self.modebox.get_active()]
        self.videoformat = self.videoformats[self.videoformatbox.get_active()]
        self.connection = self.connections[self.connectionbox.get_active()]
        self.set_title(TITLE)
        self.lostsignal = False
        self.load_playerwidget()

    def on_timer(self, timer):
        got_signal = self.playerWidget.decklink.get_property("signal")
        if not got_signal and not self.lostsignal:
            print("Lost signal")
            self.set_title("%s (No Signal)" % TITLE)
            self.lostsignal = True
        elif self.lostsignal and got_signal:
            print("Got signal")
            self.set_title(TITLE)
            self.load_playerwidget()
            self.lostsignal = False
        return True

    def load_playerwidget(self):
        if self.playerWidget is not None:
            self.playerWidget.pipeline.set_state(Gst.State.NULL)
            self.playerWidget.destroy()
            self.grid.remove(self.playerWidget)
            self.playerWidget = None
        self.playerWidget = PlayerWidget(mode=self.mode, connection=self.connection, videoformat=self.videoformat)
        self.playerWidget.set_size_request(1920, 1080)
        self.grid.attach(self.playerWidget, 0, 0, 3, 1)
        self.playerWidget.set_hexpand(True)
        self.playerWidget.set_vexpand(True)
        self.playerWidget.show()

    def on_key_release(self, widget, ev, data=None):
        key = ev.get_keycode()[1]
        print("release", key)

    def on_key_press(self, widget, ev, data=None):
        key = ev.get_keycode()[1]
        print("press", key)
        if key == 9:
            self.destroy()
        elif key == 27:
            self.load_playerwidget()
        elif key == 28:
            pass
        elif key == 41:
            if self.fullscreened:
                self.unfullscreen()
                self.fullscreened = False
                self.modebox.show()
                self.connectionbox.show()
                self.videoformatbox.show()
            else:
                self.fullscreen()
                self.fullscreened = True
                self.modebox.hide()
                self.connectionbox.hide()
                self.videoformatbox.hide()

win = MainWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
