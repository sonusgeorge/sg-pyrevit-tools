# -*- coding: utf-8 -*-
"""The SG Tools banner shown while a tool waits for a click."""

import os.path as op

import clr

# VisualTreeHelper is part of WPF. IronPython can only import from a
# .NET library after AddReference has loaded it.
clr.AddReference("PresentationCore")
from System.Windows.Media import VisualTreeHelper

from pyrevit import forms

from sgtools import STYLES

BANNER_XAML = op.join(op.dirname(__file__), "banner.xaml")


class PickBanner(forms.WPFWindow):
    """A teal banner at the top centre of Revit's drawing area.

    Open it with show(), which doesn't wait, and close it with Close()."""

    def __init__(self, message, uiapp):
        # Load the shared SG Tools look first, then the banner's layout.
        self.merge_resource_dict(STYLES)
        forms.WPFWindow.__init__(self, BANNER_XAML)
        self.message_tb.Text = message
        # Where Revit's drawing area is on the screen, in pixels.
        self.drawing_area = uiapp.DrawingAreaExtents

        # Start off-screen. window_loaded moves it into place once its
        # size is known, so it never flashes in the wrong spot.
        self.Left = -10000
        self.Top = -10000

    def window_loaded(self, sender, args):
        # Revit measures in screen pixels, WPF in its own units. On a
        # screen scaled to 150%, one WPF unit is 1.5 pixels.
        scale = VisualTreeHelper.GetDpi(self)
        area_left = self.drawing_area.Left / scale.DpiScaleX
        area_right = self.drawing_area.Right / scale.DpiScaleX
        area_top = self.drawing_area.Top / scale.DpiScaleY

        self.Left = (area_left + area_right) / 2 - self.ActualWidth / 2
        self.Top = area_top