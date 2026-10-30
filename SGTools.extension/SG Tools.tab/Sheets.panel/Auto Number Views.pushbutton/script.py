# -*- coding: utf-8 -*-
"""Number the views on a sheet by where they sit."""

__title__ = "Auto Number\nViews"
__author__ = "Sonu George"

from pyrevit import revit, DB, forms, script
from sgtools.viewports import TEMP_PREFIX, get_number, set_number
from sgtools import STYLES

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

class OrderWindow(forms.WPFWindow):
    """Asks for the reading order, with last time's choice highlighted.
    After it closes, 'choice' is "Columns first", "Rows first", or None
    if it was closed."""

    def __init__(self, last_choice):
        # Load the shared SG Tools look first, then this window's layout.
        self.merge_resource_dict(STYLES)
        forms.WPFWindow.__init__(self, "OrderWindow.xaml")
        self.choice = None

        # Make last time's choice the teal button that Enter presses.
        if last_choice == "Rows first":
            remembered = self.rows_btn
        else:
            remembered = self.columns_btn
        remembered.Style = self.FindResource("SG.PrimaryButton")
        remembered.IsDefault = True

    def columns_clicked(self, sender, args):
        self.choice = "Columns first"
        self.Close()

    def rows_clicked(self, sender, args):
        self.choice = "Rows first"
        self.Close()

    def cancel_clicked(self, sender, args):
        self.Close()

    def drag_window(self, sender, args):
        # Lets you move the window by dragging its title bar.
        self.DragMove()

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

# 3. Ask for the reading order, with last time's choice highlighted.
#    Esc or closing the window stops the tool. A new choice is
#    remembered for next time.
config = script.get_config()
window = OrderWindow(config.get_option("last_order", "Columns first"))
window.show_dialog()
choice = window.choice
if not choice:
    script.exit()
config.set_option("last_order", choice)
script.save_config()

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

# 6. Renumber as one undo step. First park every view on its own
#    temporary number, so two views never share one, even for a moment.
#    Then give each view its new number. If Revit refuses any of them,
#    the transaction undoes everything and we say so.
try:
    with revit.Transaction("Auto Number Views", log_errors=False):
        for count, viewport in enumerate(ordered, 1):
            set_number(viewport, TEMP_PREFIX + str(count))
        for count, viewport in enumerate(ordered, 1):
            set_number(viewport, str(count))
except Exception as error:
    forms.alert("Revit refused the change, so nothing was changed.\n\n"
                + str(error))