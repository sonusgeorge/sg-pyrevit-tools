# -*- coding: utf-8 -*-
"""Number the views on a sheet by where they sit."""

__title__ = "Auto Number\nViews"
__author__ = "Sonu George"

from pyrevit import revit, DB, forms
from sgtools.viewports import get_number

doc = revit.doc

# 1. Check that the open view is a sheet. If it isn't, say so and stop.
sheet = revit.active_view
if not isinstance(sheet, DB.ViewSheet):
    forms.alert(
        "Open a sheet first, then run this tool.",
        sub_msg="If you are working inside a view on a sheet, deactivate "
                "it first (right-click, Deactivate View).",
        exitscript=True)

# 2. Get the sheet's views, leaving out those with no number (legends).
#    If none are left, say so and stop.
viewports = []
for viewport_id in sheet.GetAllViewports():
    viewport = doc.GetElement(viewport_id)
    if get_number(viewport):
        viewports.append(viewport)

if not viewports:
    forms.alert("This sheet has no numbered views to renumber.",
                exitscript=True)

# For now: list what was found, to check steps 1 and 2.
for viewport in viewports:
    view = doc.GetElement(viewport.ViewId)
    print("{}  {}".format(get_number(viewport), view.Name))