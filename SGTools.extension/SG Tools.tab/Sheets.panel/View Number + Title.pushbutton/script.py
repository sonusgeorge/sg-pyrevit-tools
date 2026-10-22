from pyrevit import revit, DB, forms
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

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

    # 4. Ask for the new number. A view with no number (a legend) skips this.
    new_number = old_number
    if old_number:
        answer = forms.ask_for_string(
            default=old_number,
            prompt="Detail number:",
            title="View Number + Title")
        if answer is None:
            continue
        new_number = answer.strip()
        if not new_number:
            forms.alert("A view needs a number. Nothing was changed.")
            continue

    # 5. Ask for the new title. Empty means the sheet shows the view name.
    answer = forms.ask_for_string(
        default=old_title,
        prompt="Title on sheet (leave empty to show the view name):",
        title="View Number + Title")
    if answer is None:
        continue
    new_title = answer.strip()

    # 6. If nothing changed, go back to step 2.
    if new_number == old_number and new_title == old_title:
        continue
    
    # 7. Note which number each of the other views on this sheet has.
    #    Views without a number (legends) are left out.
    sheet = doc.GetElement(viewport.SheetId)
    others = {}
    for other_id in sheet.GetAllViewports():
        other = doc.GetElement(other_id)
        number = other.get_Parameter(DETAIL_NUMBER).AsString() or ""
        if other.Id != viewport.Id and number:
            others[number] = other

    # 8. Make the changes as one undo step. If Revit refuses any of them,
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