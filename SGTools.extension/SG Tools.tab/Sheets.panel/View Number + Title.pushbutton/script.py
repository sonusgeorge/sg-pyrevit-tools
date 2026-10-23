import clr

# Visibility (shown or collapsed) is part of WPF. IronPython can only
# import from a .NET library after AddReference has loaded it.
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

class ViewportFilter(ISelectionFilter):
    """Tells Revit which elements the user is allowed to click."""

    def AllowElement(self, element):
        return isinstance(element, DB.Viewport)

    def AllowReference(self, reference, point):
        return False

# Revit refuses two views with the same number on one sheet, even for a
# moment, so a swap parks one view on this number in between.
TEMP_NUMBER = "SG_TEMP_SWAP"

def set_number(viewport, number):
    """Set a view's Detail Number. If Revit refuses, raise an error, so the
    transaction undoes everything done so far."""
    if not viewport.get_Parameter(DETAIL_NUMBER).Set(number):
        raise Exception("Revit refused the number '{}'.".format(number))

def shown_title(viewport):
    """The title you see on the sheet: Title on Sheet, or the view's name
    when Title on Sheet is empty."""
    title = viewport.get_Parameter(TITLE_ON_SHEET).AsString()
    return title or doc.GetElement(viewport.ViewId).Name

class ViewTitleWindow(forms.WPFWindow):
    """The box that asks for the new number and title.

    'others' is the sheet's other numbered views: {number: viewport}.
    After it closes, 'result' is (number, title), or None if cancelled."""

    def __init__(self, view_name, old_number, old_title, others):
        # Load the shared SG Tools look first, then this window's layout.
        self.merge_resource_dict(STYLES)
        forms.WPFWindow.__init__(self, "ViewTitleWindow.xaml")
        self.result = None
        self.old_number = old_number
        self.others = others
        # A view with no number (a legend) can only have its title changed.
        self.has_number = bool(old_number)

        # Fill the box with what the clicked view has now. Filling the
        # number field already runs number_changed, so everything it
        # uses must be stored above this point.
        self.view_name_tb.Text = view_name
        self.number_tb.Text = old_number
        self.title_tb.Text = old_title
        if not self.has_number:
            self.number_tb.IsEnabled = False
            self.show_notice("This view has no detail number. "
                             "You can still change its title.")

    def number_changed(self, sender, args):
        # Runs on every change to the text in the number field.
        if not self.has_number:
            return
        number = self.number_tb.Text.strip()
        if not number:
            self.show_notice("Type a number. A view can't be left without one.",
                             problem=True)
        elif number != self.old_number and number in self.others:
            other_title = shown_title(self.others[number])
            self.show_notice(
                "{0} is used by {1}. The two views will swap, so {1} becomes {2}."
                .format(number, other_title, self.old_number))
        else:
            self.notice.Visibility = Visibility.Collapsed

    def show_notice(self, text, problem=False):
        """Show text under the number: teal for information, red for a problem."""
        if problem:
            back, ink = "SG.ProblemBack", "SG.ProblemInk"
        else:
            back, ink = "SG.NoticeBack", "SG.NoticeInk"
        self.notice.Background = self.FindResource(back)
        self.notice_tb.Foreground = self.FindResource(ink)
        self.notice_tb.Text = text
        self.notice.Visibility = Visibility.Visible

    def apply_clicked(self, sender, args):
        number = self.number_tb.Text.strip()
        # An empty number: the red notice already says why, so stay open.
        if self.has_number and not number:
            return
        self.result = (number, self.title_tb.Text.strip())
        self.Close()

    def cancel_clicked(self, sender, args):
        self.Close()

# 1. Check that the open view is a sheet. If it isn't, say so and stop.
if not isinstance(revit.active_view, DB.ViewSheet):
    forms.alert("Open a sheet first, then run this tool.", exitscript=True)



while True:
    # 2. Wait for a click on a view on the sheet. Esc stops the tool.
    try:
        reference = uidoc.Selection.PickObject(
            ObjectType.Element,
            ViewportFilter(),
            "Pick a view. Esc to finish.")
    except OperationCanceledException:
        break
    viewport = doc.GetElement(reference)

    # 3. Read the view's Detail Number and Title on Sheet.
    number_param = viewport.get_Parameter(DETAIL_NUMBER)
    title_param = viewport.get_Parameter(TITLE_ON_SHEET)
    old_number = number_param.AsString() or ""
    old_title = title_param.AsString() or ""

    # 4. Note which number each of the other views on this sheet has, so
    #    the box can warn about a swap. Views without a number (legends)
    #    are left out.
    sheet = doc.GetElement(viewport.SheetId)
    others = {}
    for other_id in sheet.GetAllViewports():
        other = doc.GetElement(other_id)
        number = other.get_Parameter(DETAIL_NUMBER).AsString() or ""
        if other.Id != viewport.Id and number:
            others[number] = other

    # 5. Show the box with the current values and wait for Apply or
    #    Cancel. Cancel goes back to step 2.
    view = doc.GetElement(viewport.ViewId)
    window = ViewTitleWindow(view.Name, old_number, old_title, others)
    window.show_dialog()
    if window.result is None:
        continue
    new_number, new_title = window.result

    # 6. If nothing changed, go back to step 2.
    if new_number == old_number and new_title == old_title:
        continue

    # 7. Make the changes as one undo step. If Revit refuses any of them,
    #    the transaction undoes them all and we say so.
    try:
        with revit.Transaction("View Number + Title", log_errors=False):
            if new_number != old_number:
                other = others.get(new_number)
                if other is None:
                    set_number(viewport, new_number)
                else:
                    set_number(other, TEMP_NUMBER)
                    set_number(viewport, new_number)
                    set_number(other, old_number)
            if new_title != old_title:
                title_param.Set(new_title)
    except Exception as error:
        forms.alert("Revit refused the change, so nothing was changed.\n\n"
                    + str(error))