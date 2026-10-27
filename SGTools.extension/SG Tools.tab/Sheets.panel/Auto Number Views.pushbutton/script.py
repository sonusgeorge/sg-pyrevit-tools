# -*- coding: utf-8 -*-
"""Number the views on a sheet by where they sit."""

__title__ = "Auto Number\nViews"
__author__ = "Sonu George"

from pyrevit import revit, DB, forms, script
from sgtools.viewports import get_number

doc = revit.doc

def centre(viewport, axis):
    """Where the middle of the view's box is on the sheet, across ("x")
    or up ("y")."""
    point = viewport.GetBoxCenter()
    return point.X if axis == "x" else point.Y


def span(viewport, axis):
    """Where the view's box starts and ends on the sheet, across ("x")
    or up ("y")."""
    box = viewport.GetBoxOutline()
    if axis == "x":
        return box.MinimumPoint.X, box.MaximumPoint.X
    return box.MinimumPoint.Y, box.MaximumPoint.Y


def group(viewports, axis):
    """Split the views into columns (axis "x") or rows (axis "y").
    Going from left to right (or bottom to top), a view joins the last
    group if its centre falls within the box of that group's first view;
    otherwise it starts a new group."""
    groups = []
    for viewport in sorted(viewports, key=lambda v: centre(v, axis)):
        if groups:
            low, high = span(groups[-1][0], axis)
            if low <= centre(viewport, axis) <= high:
                groups[-1].append(viewport)
                continue
        groups.append([viewport])
    return groups

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

# 3. Ask for the reading order. Esc or closing the window stops the tool.
choice = forms.CommandSwitchWindow.show(
    ["Columns first", "Rows first"],
    message="Number the views on this sheet:")
if not choice:
    script.exit()

# 4 and 5. Group the views into columns or rows, then put them in
#    reading order.
ordered = []
if choice == "Columns first":
    # Columns left to right, each column top to bottom.
    for column in group(viewports, "x"):
        ordered += sorted(column, key=lambda v: centre(v, "y"), reverse=True)
else:
    # Rows top to bottom, each row left to right.
    rows = group(viewports, "y")
    rows.reverse()
    for row in rows:
        ordered += sorted(row, key=lambda v: centre(v, "x"))

# For now: show the new order, to check steps 3 to 5.
for new_number, viewport in enumerate(ordered, 1):
    view = doc.GetElement(viewport.ViewId)
    print("{}  {}  (now {})".format(new_number, view.Name, get_number(viewport)))