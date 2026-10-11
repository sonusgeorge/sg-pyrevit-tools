# -*- coding: utf-8 -*-
"""Change the Detail Number and Title on Sheet of views on a sheet.

Pick a view, then type its new number and title. If another view on
the sheet already has that number, the two views swap numbers.
Press Esc to finish."""

__title__ = "View Number\n+ Title"

import re

import clr

# Visibility is part of WPF, Windows' library for building windows.
# IronPython can only import from a .NET library after being told to
# load it, which is what AddReference does.
clr.AddReference("PresentationCore")
from System.Windows import Visibility

from pyrevit import revit, DB, forms
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from sgtools import STYLES

doc = revit.doc
uidoc = revit.uidoc

# Revit's internal names for the two parameters this tool changes.
DETAIL_NUMBER = DB.BuiltInParameter.VIEWPORT_DETAIL_NUMBER
TITLE_ON_SHEET = DB.BuiltInParameter.VIEW_DESCRIPTION

# Revit refuses two views with the same number on one sheet, even for a
# moment, so a swap parks one view on this number in between.
TEMP_NUMBER = "SG_TEMP_SWAP"

TOOL_NAME = "View Number + Title"


class ViewportFilter(ISelectionFilter):
    """Tells Revit which elements the user is allowed to click."""

    def AllowElement(self, element):
        return isinstance(element, DB.Viewport)

    def AllowReference(self, reference, point):
        return False


def get_number(viewport):
    """The view's Detail Number. Empty text for a view that has none,
    such as a legend."""
    return viewport.get_Parameter(DETAIL_NUMBER).AsString() or ""


def set_number(viewport, number):
    # Set() returns False when Revit refuses the value. Raising an error
    # here makes the transaction undo everything it has done so far.
    if not viewport.get_Parameter(DETAIL_NUMBER).Set(number):
        raise Exception("Revit refused the number '{}'.".format(number))


def free_temp_number(numbers_in_use):
    """A temporary number that no view on the sheet is using."""
    number = TEMP_NUMBER
    while number in numbers_in_use:
        number += "_"
    return number


def get_title_on_sheet(view):
    """What is typed in Title on Sheet. Empty text if nothing is."""
    return view.get_Parameter(TITLE_ON_SHEET).AsString() or ""


def get_shown_title(viewport):
    """The title you see on the sheet: Title on Sheet, or the view name."""
    view = doc.GetElement(viewport.ViewId)
    return get_title_on_sheet(view) or view.Name


def describe_view_type(view):
    """Turn Revit's 'FloorPlan' into 'floor plan' for the box."""
    name = str(view.ViewType)
    special = {"ThreeD": "3D view", "EngineeringPlan": "structural plan"}
    if name in special:
        return special[name]
    return re.sub("([a-z])([A-Z])", r"\1 \2", name).lower()


class ViewTitleWindow(forms.WPFWindow):
    """The box that asks for the new number and title.

    After it closes, 'result' is (number, title), or None if cancelled."""

    def __init__(self, view_name, view_type, old_number, old_title, numbers_in_use):
        # Load the shared SG Tools look first, then this window's layout.
        self.merge_resource_dict(STYLES)
        forms.WPFWindow.__init__(self, "ViewTitleWindow.xaml")

        self.old_number = old_number
        self.numbers_in_use = numbers_in_use
        self.result = None
        # A view with no number (a legend) can only have its title changed.
        self.has_number = bool(old_number)

        # Fill the box with what the picked view has now.
        self.view_name_run.Text = view_name
        self.view_type_run.Text = view_type
        self.title_hint.Text = view_name
        self.title_tb.Text = old_title
        self.number_tb.Text = old_number

        if not self.has_number:
            self.number_tb.IsEnabled = False
            self.show_notice("This view has no detail number. "
                             "You can still change its title.")

    def window_loaded(self, sender, args):
        # Put the cursor in the number field with the number selected,
        # so typing replaces it. Without a number, start in the title.
        field = self.number_tb if self.has_number else self.title_tb
        field.Focus()
        field.SelectAll()

    def number_changed(self, sender, args):
        # Runs on every keystroke in the number field.
        if not self.has_number:
            return
        number = self.number_tb.Text.strip()
        if not number:
            self.show_notice("Type a number. A view can't be left without one.",
                             problem=True)
        elif number != self.old_number and number in self.numbers_in_use:
            other_title = self.numbers_in_use[number]
            self.show_notice(
                "{0} is used by {1}. The two views will swap, so {1} becomes {2}."
                .format(number, other_title, self.old_number))
        else:
            self.notice.Visibility = Visibility.Collapsed

    def show_notice(self, text, problem=False):
        kind = "Problem" if problem else "Notice"
        self.notice.Background = self.FindResource("SG.{}Back".format(kind))
        self.notice_tb.Foreground = self.FindResource("SG.{}Ink".format(kind))
        self.notice_tb.Text = text
        self.notice.Visibility = Visibility.Visible

    def apply(self, sender, args):
        number = self.number_tb.Text.strip()
        if self.has_number and not number:
            return
        self.result = (number, self.title_tb.Text.strip())
        self.Close()

    def cancel(self, sender, args):
        self.Close()

    def drag_window(self, sender, args):
        self.DragMove()


# 1. Check that the open view is a sheet. If it isn't, say so and stop.
if not isinstance(revit.active_view, DB.ViewSheet):
    forms.alert(
        "Open a sheet first, then run this tool.",
        sub_msg="If you are working inside a view on a sheet, deactivate "
                "it first (right-click, Deactivate View).",
        exitscript=True)

# 2. Show a banner at the top of Revit.
with forms.WarningBar(title="Pick a view to renumber. Esc to finish."):
    while True:
        # 3. Wait for a click on a view. Esc ends the tool.
        try:
            reference = uidoc.Selection.PickObject(
                ObjectType.Element,
                ViewportFilter(),
                "Pick a view to renumber. Esc to finish.")
        except OperationCanceledException:
            break
        picked = doc.GetElement(reference)
        view = doc.GetElement(picked.ViewId)

        # 4. Read the picked view's current number and title.
        old_number = get_number(picked)
        old_title = get_title_on_sheet(view)

        # 5. Note which number each of the other views on this sheet has.
        #    Views without a number (legends) are left out.
        sheet = doc.GetElement(picked.SheetId)
        others = {}
        for viewport_id in sheet.GetAllViewports():
            viewport = doc.GetElement(viewport_id)
            number = get_number(viewport)
            if viewport.Id != picked.Id and number:
                others[number] = viewport

        # 6. Show the box and wait for Apply or Cancel.
        window = ViewTitleWindow(
            view.Name,
            describe_view_type(view),
            old_number,
            old_title,
            {number: get_shown_title(vp) for number, vp in others.items()})
        window.show_dialog()

        # Cancelled or nothing changed: change nothing, pick again.
        if window.result is None:
            continue
        new_number, new_title = window.result
        if new_number == old_number and new_title == old_title:
            continue

        # 7. Make the changes as one undo step. If Revit refuses any of
        #    them, the transaction undoes them all and we say so.
        try:
            with revit.Transaction(TOOL_NAME, log_errors=False):
                if new_number != old_number:
                    other = others.get(new_number)
                    if other is None:
                        set_number(picked, new_number)
                    else:
                        set_number(other, free_temp_number(others))
                        set_number(picked, new_number)
                        set_number(other, old_number)
                if new_title != old_title:
                    view.get_Parameter(TITLE_ON_SHEET).Set(new_title)
        except Exception as error:
            forms.alert("Revit refused the change, so nothing was changed.",
                        sub_msg=str(error))

        # 8. Back to step 3.
