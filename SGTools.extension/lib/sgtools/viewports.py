# -*- coding: utf-8 -*-
"""Reading and safely setting the Detail Numbers of views on a sheet.
Shared by the SG Tools buttons that renumber views."""

from pyrevit import DB

# Revit's internal name for a view's Detail Number on a sheet.
DETAIL_NUMBER = DB.BuiltInParameter.VIEWPORT_DETAIL_NUMBER

# Revit refuses two views with the same number on one sheet, even for a
# moment, so a view is parked on a temporary number while others move.
# Each temporary number starts with this, followed by something unique.
TEMP_PREFIX = "SG_TEMP_"


def get_number(viewport):
    """A view's Detail Number, or "" if it has none (a legend)."""
    return viewport.get_Parameter(DETAIL_NUMBER).AsString() or ""


def set_number(viewport, number):
    """Set a view's Detail Number. If Revit refuses, raise an error, so the
    transaction undoes everything done so far."""
    if not viewport.get_Parameter(DETAIL_NUMBER).Set(number):
        raise Exception("Revit refused the number '{}'.".format(number))