# -*- coding: utf-8 -*-
#Copyright (c) 2011 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import gtk
import gobject
import os

import pango

import sugar
from sugar.activity import activity
from sugar import profile
try:
    from sugar.graphics.toolbarbox import ToolbarBox
    _have_toolbox = True
except ImportError:
    _have_toolbox = False

if _have_toolbox:
    from sugar.bundle.activitybundle import ActivityBundle
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton
    from sugar.graphics.toolbarbox import ToolbarButton

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.datastore import datastore
from sugar import mime

from sprites import Sprites, Sprite

from gettext import gettext as _

try:
    from sugar.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

SERVICE = 'org.sugarlabs.PortfolioActivity'
IFACE = SERVICE
PATH = '/org/augarlabs/PortfolioActivity'


def _svg_str_to_pixbuf(svg_string):
    ''' Load pixbuf from SVG string '''
    pl = gtk.gdk.PixbufLoader('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf


def _load_svg_from_file(file_path, width, height):
    '''Create a pixbuf from SVG in a file. '''
    return gtk.gdk.pixbuf_new_from_file_at_size(file_path, width, height)


def _button_factory(icon_name, tooltip, callback, toolbar, cb_arg=None,
                    accelerator=None):
    '''Factory for making toolbar buttons'''
    my_button = ToolButton(icon_name)
    my_button.set_tooltip(tooltip)
    my_button.props.sensitive = True
    if accelerator is not None:
        my_button.props.accelerator = accelerator
    if cb_arg is not None:
        my_button.connect('clicked', callback, cb_arg)
    else:
        my_button.connect('clicked', callback)
    if hasattr(toolbar, 'insert'):  # the main toolbar
        toolbar.insert(my_button, -1)
    else:  # or a secondary toolbar
        toolbar.props.page.insert(my_button, -1)
    my_button.show()
    return my_button


def _label_factory(label, toolbar):
    ''' Factory for adding a label to a toolbar '''
    my_label = gtk.Label(label)
    my_label.set_line_wrap(True)
    my_label.show()
    toolitem = gtk.ToolItem()
    toolitem.add(my_label)
    toolbar.insert(toolitem, -1)
    toolitem.show()
    return my_label


def _separator_factory(toolbar, visible=True, expand=False):
    ''' Factory for adding a separator to a toolbar '''
    separator = gtk.SeparatorToolItem()
    separator.props.draw = visible
    separator.set_expand(expand)
    toolbar.insert(separator, -1)
    separator.show()


class PortfolioActivity(activity.Activity):
    ''' Portfolio's bones: Portfolio's bones were invented by John Portfolio
    (1550-1617), a Scottish mathematician and scientist. They help you
    to do multiplication. '''

    # TODO: Define your own bone.

    def __init__(self, handle):
        ''' Initialize the toolbars and the work surface '''
        super(PortfolioActivity, self).__init__(handle)

        self._setup_toolbars(_have_toolbox)
        self._setup_canvas()
        self._setup_workspace()

    def _setup_canvas(self):
        ''' Create a canvas '''

        self._canvas = gtk.DrawingArea()
        self._canvas.set_size_request(gtk.gdk.screen_width(),
                                      gtk.gdk.screen_height())
        self.set_canvas(self._canvas)
        self._canvas.show()
        self.show_all()

        self._canvas.set_flags(gtk.CAN_FOCUS)
        self._canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self._canvas.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self._canvas.connect("expose-event", self._expose_cb)
        # self._canvas.connect("motion-notify-event", self._mouse_move_cb)
        # self._canvas.connect("key_press_event", self._key_press_cb)

    def _setup_workspace(self):
        ''' Prepare to render the datastore entries. '''
        self._width = gtk.gdk.screen_width()
        self._height = gtk.gdk.screen_height()
        self._scale = gtk.gdk.screen_width()/1200.

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)

        self._preview = None
        self._title = Sprite(self._sprites, 0, 0, _svg_str_to_pixbuf(
                _genblank(self._width - 300, 40)))
        self._description = Sprite(self._sprites, 0, 0, _svg_str_to_pixbuf(
                _genblank(self._width - 300, self._height - 225)))
        self._my_canvas = Sprite(self._sprites, 0, 0,
                                gtk.gdk.Pixmap(self._canvas.window,
                                               self._width,
                                               self._height, -1))
        self._my_canvas.set_layer(0)
        self._my_gc = self._my_canvas.images[0].new_gc()

        self._my_canvas.set_layer(1)
        self._text_color = self._my_gc.get_colormap().alloc_color('#000000')
        self._fd = pango.FontDescription('Sans')

        self._clear_screen()

        self._find_starred()
        self.i = 0
        self._show_slide(self.i)

    def _setup_toolbars(self, have_toolbox):
        ''' Setup the toolbars. '''

        self.max_participants = 1  # no sharing

        if have_toolbox:
            toolbox = ToolbarBox()

            # Activity toolbar
            activity_button = ActivityToolbarButton(self)

            toolbox.toolbar.insert(activity_button, 0)
            activity_button.show()

            self.set_toolbar_box(toolbox)
            toolbox.show()
            self.toolbar = toolbox.toolbar

        else:
            # Use pre-0.86 toolbar design
            self.toolbar = gtk.Toolbar()
            toolbox.add_toolbar(_('Page'), primary_toolbar)
            toolbox.show()
            toolbox = activity.ActivityToolbox(self)
            self.set_toolbox(toolbox)
            toolbox.show()
            toolbox.set_current_toolbar(1)

        self._prev_button = _button_factory(
            'go-previous', _('Prev slide'), self._prev_cb,
            self.toolbar)

        self._next_button = _button_factory(
            'go-next', _('Next slide'), self._next_cb,
            self.toolbar)

        if _have_toolbox:
            _separator_factory(toolbox.toolbar, False, True)

            stop_button = StopButton(self)
            stop_button.props.accelerator = '<Ctrl>q'
            toolbox.toolbar.insert(stop_button, -1)
            stop_button.show()

    def _key_press_cb(self, win, event):
        ''' TODO: '''
        return True

    def _expose_cb(self, win, event):
        ''' Have to refresh after a change in window status. '''
        self._sprites.redraw_sprites()
        return True

    def _destroy_cb(self, win, event):
        gtk.main_quit()

    def _find_starred(self):
        self._dsobjects, self._nobjects = datastore.find({'keep':'1'})
        return

    def _prev_cb(self, button=None):
        if self.i > 0:
            self.i -= 1
            self._show_slide(self.i)

    def _next_cb(self, button=None):
        if self.i < self._nobjects:
            self.i += 1
            self._show_slide(self.i)

    def _clear_screen(self):
        self._my_gc.set_foreground(
            self._my_gc.get_colormap().alloc_color('#FFFFFF'))
        rect = gtk.gdk.Rectangle(0, 0, self._width, self._height)
        self._my_canvas.images[0].draw_rectangle(self._my_gc, True, *rect)
        self.invalt(0, 0, self._width, self._height)

    def _show_slide(self, i):
        self._clear_screen()
        print self._dsobjects[i].metadata['title']

        pixbuf = get_pixbuf_from_journal(self._dsobjects[i], 300, 225)
        if pixbuf is not None:
            if self._preview is None:
                self._preview = Sprite(self._sprites, 0, 0, pixbuf)
            else:
                self._preview.images[0] = pixbuf
                self._preview.move((0, 0))
            self._preview.set_layer(1000)
        else:
            if self._preview is not None:
                self._preview.hide()
            print 'pixbuf is None'
        self._title.move((300, 0))
        self._title.set_label(self._dsobjects[i].metadata['title'])
        self._title.set_layer(1000)
        if 'description' in self._dsobjects[i].metadata:
            self._description.move((300, 40))
            self._description.set_label(
                self._dsobjects[i].metadata['description'])
            self._description.set_layer(1000)
        else:
            self._description.set_label('')
            self._description.hide()
            print 'description is None'

    def invalt(self, x, y, w, h):
        ''' Mark a region for refresh '''
        self._canvas.window.invalidate_rect(
            gtk.gdk.Rectangle(int(x), int(y), int(w), int(h)), False)


def get_pixbuf_from_journal(dsobject, w, h):
    """ Load a pixbuf from a Journal object. """
    # _pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(dsobject.file_path,
    try:
        _pixbufloader = \
            gtk.gdk.pixbuf_loader_new_with_mime_type('image/png')
        _pixbufloader.set_size(min(300, int(w)), min(225, int(h)))
        _pixbufloader.write(dsobject.metadata['preview'])
        _pixbufloader.close()
        _pixbuf = _pixbufloader.get_pixbuf()
    except:
        _pixbuf = None
    return _pixbuf


def _genblank(w, h):
    svg = SVG()
    svg_string = svg.header(w, h)
    svg_string += svg.footer()
    return svg_string


class SVG:
    ''' SVG generators '''

    def __init__(self):
        self._scale = 1
        self._stroke_width = 1
        self._fill = '#FFFFFF'
        self._stroke = '#000000'

    def _svg_style(self, extras=""):
        return "%s%s%s%s%s%f%s%s%s" % ("style=\"fill:", self._fill, ";stroke:",
                                       self._stroke, ";stroke-width:",
                                       self._stroke_width, ";", extras,
                                       "\" />\n")

    def _svg_rect(self, w, h, rx, ry, x, y):
        svg_string = "       <rect\n"
        svg_string += "          width=\"%f\"\n" % (w)
        svg_string += "          height=\"%f\"\n" % (h)
        svg_string += "          rx=\"%f\"\n" % (rx)
        svg_string += "          ry=\"%f\"\n" % (ry)
        svg_string += "          x=\"%f\"\n" % (x)
        svg_string += "          y=\"%f\"\n" % (y)
        self.set_stroke_width(1.0)
        svg_string += self._svg_style()
        return svg_string

    def _background(self, w=80, h=60, scale=1):
        return self._svg_rect((w - 0.5) * scale, (h - 0.5) * scale,
                              1, 1, 0.25, 0.25)

    def header(self, w=80, h=60, scale=1, background=True):
        svg_string = "<?xml version=\"1.0\" encoding=\"UTF-8\""
        svg_string += " standalone=\"no\"?>\n"
        svg_string += "<!-- Created with Emacs -->\n"
        svg_string += "<svg\n"
        svg_string += "   xmlns:svg=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   xmlns=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   version=\"1.0\"\n"
        svg_string += "%s%f%s" % ("   width=\"", scale * w * self._scale,
                                  "\"\n")
        svg_string += "%s%f%s" % ("   height=\"", scale * h * self._scale,
                                  "\">\n")
        svg_string += "%s%f%s%f%s" % ("<g\n       transform=\"matrix(",
                                      self._scale, ",0,0,", self._scale,
                                      ",0,0)\">\n")
        if background:
            svg_string += self._background(w, h, scale)
        return svg_string

    def footer(self):
        svg_string = "</g>\n"
        svg_string += "</svg>\n"
        return svg_string

    def set_scale(self, scale=1.0):
        self._scale = scale

    def set_colors(self, colors):
        self._stroke = colors[0]
        self._fill = colors[1]

    def set_stroke_width(self, stroke_width=1.0):
        self._stroke_width = stroke_width
