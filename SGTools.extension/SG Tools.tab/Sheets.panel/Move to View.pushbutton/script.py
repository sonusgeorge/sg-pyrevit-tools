# -*- coding: utf-8 -*-
__doc__ = """Move annotations drawn on a sheet into the view underneath.
____________________________________________________________________
What it does:
Text notes and detail lines drawn on the sheet by mistake stay
behind when the view is moved. This tool moves them into the view,
in the same place on the paper and at the same printed size, so
from then on they move with the view.
____________________________________________________________________
How to use:
1. Open the sheet and select the annotations. Or click this button
   first, select them, then click Finish.
2. Click the view to move them into.
3. A teal banner says how many were moved.
____________________________________________________________________
Good to know:
- Only text notes and detail lines drawn on the sheet itself can
  be picked.
- Works with plan, section, elevation, detail and drafting views,
  but not with a view whose crop region is split.
- If an annotation lies outside the view, you are asked first:
  the view's crop region may hide it.
- Text notes keep their type and leaders. Lines keep their style.
- Everything is one undo step (Ctrl+Z).
____________________________________________________________________
Version 1.0 (November 2026). Tested in Revit 2024 and 2027.
Press F1 for the full guide."""
__title__ = "Move to\nView"
__author__ = "Sonu George"
__helpurl__ = "https://github.com/sonusgeorge/sg-pyrevit-tools#move-to-view"

import math

from System.Collections.Generic import List

from pyrevit import revit, DB, forms, script
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from sgtools.banner import PickBanner

doc = revit.doc
uidoc = revit.uidoc

# The kinds of view this tool can move annotations into.
TARGET_VIEW_TYPES = (
    DB.ViewType.FloorPlan,
    DB.ViewType.CeilingPlan,
    DB.ViewType.EngineeringPlan,
    DB.ViewType.AreaPlan,
    DB.ViewType.Section,
    DB.ViewType.Elevation,
    DB.ViewType.Detail,
    DB.ViewType.DraftingView,
)


def is_movable(element, sheet):
    """True for a text note or detail line that was drawn on this sheet
    itself, not inside one of its views."""
    if not isinstance(element, (DB.TextNote, DB.DetailCurve)):
        return False
    return element.OwnerViewId == sheet.Id


def is_inside(element, sheet, viewport):
    """True if the element lies wholly inside the view's box on the
    sheet."""
    element_box = element.get_BoundingBox(sheet)
    view_box = viewport.GetBoxOutline()
    return (view_box.MinimumPoint.X <= element_box.Min.X
            and element_box.Max.X <= view_box.MaximumPoint.X
            and view_box.MinimumPoint.Y <= element_box.Min.Y
            and element_box.Max.Y <= view_box.MaximumPoint.Y)


class AnnotationFilter(ISelectionFilter):
    """Lets the user click only text notes and detail lines that belong
    to the sheet."""

    def __init__(self, sheet):
        self.sheet = sheet

    def AllowElement(self, element):
        return is_movable(element, self.sheet)

    def AllowReference(self, reference, point):
        return False


class ViewportFilter(ISelectionFilter):
    """Lets the user click only views on the sheet."""

    def AllowElement(self, element):
        return isinstance(element, DB.Viewport)

    def AllowReference(self, reference, point):
        return False


def onto_plane(point, plane_point, normal):
    """The point moved straight onto the view's plane (the flat surface
    the view draws on), which passes through plane_point and faces
    along normal."""
    distance = (point - plane_point).DotProduct(normal)
    return point - normal * distance


def move_note(note, sheet, view, sheet_to_model):
    """Copy a text note from the sheet into the view, then put it and
    its leaders where they were on the paper."""
    copy_id = DB.ElementTransformUtils.CopyElements(
        sheet, List[DB.ElementId]([note.Id]), view, None, None)[0]
    copy = doc.GetElement(copy_id)

    # Revit puts the copy on the view's plane, but at the note's sheet
    # numbers. Remember that plane, then move the copy to its converted
    # point, kept on the plane.
    plane_point = copy.Coord
    normal = view.ViewDirection
    target = onto_plane(sheet_to_model.OfPoint(note.Coord),
                        plane_point, normal)
    DB.ElementTransformUtils.MoveElement(doc, copy_id, target - copy.Coord)

    # In a viewport turned on the sheet, the copy comes in turned too.
    # Turn it about its own point so it reads the same way on the paper
    # as before.
    wanted = sheet_to_model.OfVector(note.BaseDirection)
    turn = copy.BaseDirection.AngleOnPlaneTo(wanted, normal)
    axis = DB.Line.CreateUnbound(copy.Coord, normal)
    DB.ElementTransformUtils.RotateElement(doc, copy_id, axis, turn)

    # The leaders kept their paper lengths, so at 1:100 they are 100
    # times too short. Put each end and elbow on its converted point.
    for old, new in zip(note.GetLeaders(), copy.GetLeaders()):
        new.End = onto_plane(sheet_to_model.OfPoint(old.End),
                             plane_point, normal)
        new.Elbow = onto_plane(sheet_to_model.OfPoint(old.Elbow),
                               plane_point, normal)


def move_line(line, view, sheet_to_model):
    """Draw the detail line again inside the view, at its converted size
    and place, with the same line style."""
    curve = line.GeometryCurve.CreateTransformed(sheet_to_model)
    new_line = doc.Create.NewDetailCurve(view, curve)
    new_line.LineStyle = line.LineStyle


def get_sheet_to_model(viewport, view):
    """The conversion from a point on the sheet to the same point inside
    the view (in model coordinates)."""
    if view.ViewType != DB.ViewType.DraftingView:
        # Revit gives it in two steps: model to paper inside the view
        # (this step holds the scale), and paper inside the view to
        # sheet (where the view sits on the sheet). Joined and turned
        # round, they convert sheet to model.
        model_to_paper = (view.GetModelToProjectionTransforms()[0]
                          .GetModelToProjectionTransform())
        paper_to_sheet = viewport.GetProjectionToSheetTransform()
        return paper_to_sheet.Multiply(model_to_paper).Inverse

    # A drafting view has no model, so Revit gives no conversion. Build
    # the same two steps by hand. Model to paper is just the scale.
    model_to_paper = DB.Transform.Identity.ScaleBasis(1.0 / view.Scale)

    # Paper to sheet: the middle of the view's box on the sheet shows
    # the middle of its drawing (view.Outline, measured on paper).
    outline = view.Outline
    drawing_middle = DB.XYZ((outline.Min.U + outline.Max.U) / 2,
                            (outline.Min.V + outline.Max.V) / 2, 0)
    if viewport.Rotation == DB.ViewportRotation.Clockwise:
        turn = -math.pi / 2
    elif viewport.Rotation == DB.ViewportRotation.Counterclockwise:
        turn = math.pi / 2
    else:
        turn = 0.0
    # Read these three from the bottom up: move the drawing's middle to
    # the origin, turn it like the viewport, then move it to the middle
    # of the box.
    paper_to_sheet = (
        DB.Transform.CreateTranslation(viewport.GetBoxCenter())
        .Multiply(DB.Transform.CreateRotation(DB.XYZ.BasisZ, turn))
        .Multiply(DB.Transform.CreateTranslation(drawing_middle.Negate())))
    return paper_to_sheet.Multiply(model_to_paper).Inverse


# 1. Check that the open view is a sheet. If it isn't, say so and stop.
sheet = revit.active_view
if not isinstance(sheet, DB.ViewSheet):
    forms.alert(
        "Open a sheet first, then run this tool.",
        sub_msg="If you are working inside a view on a sheet, deactivate "
                "it first (right-click, Deactivate View).",
        exitscript=True)

# 2. Get the annotations. Use the ones already selected, if any are
#    text notes or detail lines on this sheet. Otherwise ask the user to
#    pick them, then click Finish. Nothing picked, or Esc: stop quietly.
annotations = []
for element_id in uidoc.Selection.GetElementIds():
    element = doc.GetElement(element_id)
    if is_movable(element, sheet):
        annotations.append(element)

if not annotations:
    banner = PickBanner("Select the annotations to move, then click Finish",
                        __revit__, hint="Esc to cancel")
    banner.show()
    try:
        references = uidoc.Selection.PickObjects(
            ObjectType.Element,
            AnnotationFilter(sheet),
            "Select text notes and detail lines. Click Finish when done.")
    except OperationCanceledException:
        script.exit()
    finally:
        banner.Close()

    for reference in references:
        annotations.append(doc.GetElement(reference))
    if not annotations:
        script.exit()

# 3. Ask the user to click the view to move them into. Esc: stop.
banner = PickBanner("Click the view to move them into", __revit__,
                    hint="Esc to cancel")
banner.show()
try:
    reference = uidoc.Selection.PickObject(
        ObjectType.Element,
        ViewportFilter(),
        "Click the target view. Esc to cancel.")
except OperationCanceledException:
    script.exit()
finally:
    banner.Close()

viewport = doc.GetElement(reference)
view = doc.GetElement(viewport.ViewId)

# 4. Check the view can take the annotations: it must be a plan,
#    section, elevation, detail or drafting view, and its crop region
#    must not be split into parts (each part has its own conversion).
if view.ViewType not in TARGET_VIEW_TYPES:
    forms.alert(
        "This tool can't move annotations into a {} view.".format(
            view.ViewType),
        sub_msg="Pick a plan, section, elevation, detail or drafting view.",
        exitscript=True)

if (view.ViewType != DB.ViewType.DraftingView
        and view.GetModelToProjectionTransforms().Count != 1):
    forms.alert(
        "The crop region of {} is split into parts.".format(view.Name),
        sub_msg="This tool can't move annotations into a view with a "
                "split crop region yet.",
        exitscript=True)

# 5. Work out the sheet to model conversion for this view.
sheet_to_model = get_sheet_to_model(viewport, view)

# 6. If any annotation lies outside the view's box on the sheet, the
#    wrong view may have been clicked, and inside the view the crop
#    region may hide it. Ask before going on.
outside = 0
for annotation in annotations:
    if not is_inside(annotation, sheet, viewport):
        outside += 1

if outside:
    go_on = forms.alert(
        "{} of the {} annotations lie outside {} on the sheet.".format(
            outside, len(annotations), view.Name),
        sub_msg="Check that you clicked the right view. Inside the view, "
                "the crop region may hide them.\n\nMove them anyway?",
        yes=True, no=True)
    if not go_on:
        script.exit()

# 7. Move everything as one undo step: copy or redraw each annotation
#    inside the view, then delete the original from the sheet. If Revit
#    refuses any part, the transaction undoes all of it and we say so.
try:
    with revit.Transaction("Move to View", log_errors=False):
        for annotation in annotations:
            if isinstance(annotation, DB.TextNote):
                move_note(annotation, sheet, view, sheet_to_model)
            else:
                move_line(annotation, view, sheet_to_model)
            doc.Delete(annotation.Id)
except Exception as error:
    forms.alert("Revit refused the change, so nothing was moved.\n\n"
                + str(error))
else:
    # 8. Runs only if nothing went wrong: say what moved where, in a
    #    teal banner that closes by itself after 3 seconds.
    if len(annotations) == 1:
        moved_text = "1 annotation"
    else:
        moved_text = "{} annotations".format(len(annotations))
    done = PickBanner("Moved {} into {}.".format(moved_text, view.Name),
                      __revit__, hint="")
    done.show_for(3)
