# SG Tools (pyRevit)

A pyRevit extension of Revit tools for architectural and structural modelling. I'm building it to learn the Revit API, one small tool at a time.

Each tool here is rebuilt in C# in [sg-csharp-tools](https://github.com/sonusgeorge/sg-csharp-tools).

## Tools

### View Number + Title

**Ribbon:** SG Tools tab, Sheets panel

**The problem.** Revit won't let two views on a sheet share a Detail Number. To put the views on a sheet in order you have to park one view on a throwaway number, renumber the next, and come back to the first. On a sheet with six or eight views that turns into a long chain of temporary numbers.

**What the tool does.** Pick a view on the sheet and type its new number. If another view already has that number, the two swap, and the tool handles the temporary number itself. The same box also changes the view's Title on Sheet.

![Picking two views on a sheet, swapping their numbers and changing their titles](docs/view-number-title/demo.gif)

<img src="docs/view-number-title/box.png" alt="The View Number + Title box, showing a notice that number 3 is used by East and the two views will swap" width="400">

**How to use it**

1. Open a sheet and click **View Number + Title**.
2. Click a view on the sheet.
3. Type the new number, the new title, or both. A notice tells you before you apply if the number belongs to another view and the two will swap.
4. Press Enter to apply. The tool goes straight back to waiting for the next view.
5. Press Esc when you're done.

Each change is one undo step, so Ctrl+Z takes back one view at a time.

**Good to know**

- Legends have no Detail Number, so for a legend the number field is greyed out and only the title can be changed.
- Leaving Title on Sheet empty shows the view's own name on the sheet.
- Revit treats `1` and `01`, and `a1` and `A1`, as different numbers, so the tool does too.

**Tested in:** Revit 2027, in full. Also run in Revit 2024, where it works, though without the full round of tests. Written to be compatible with Revit 2025 and 2026, but not yet run in them.

**What building it taught**

- The thing you click on a sheet is a `Viewport`, a separate element that places a view on a sheet. It is not the view itself.
- Revit has two parameters both shown as "Detail Number". Only `VIEWPORT_DETAIL_NUMBER` can be changed; its twin `VIEWER_DETAIL_NUMBER` is read-only. Code has to use the internal name, because the visible name doesn't say which one you get.
- Code can only change a Revit model inside a transaction, and each transaction is one entry in the Undo list. Keeping related changes in one transaction also means a failed change undoes the others.
- When Revit rejects a value it doesn't raise an error. It returns `False` and may show its own pop-up, so the code has to check the value first.
- A selection filter decides what the user is allowed to click, which also protects the rest of the code from elements it can't handle.
- A window is described in XAML, a layout file with no logic, and the Python class behind it supplies the behaviour. The shared colours and styles live in one file so every tool looks the same.

## Install

1. Install [pyRevit](https://github.com/pyrevitlabs/pyRevit).
2. Download or clone this repository.
3. In Revit, open the pyRevit tab, then Settings, and add the downloaded folder under Custom Extension Directories.
4. Save the settings and reload pyRevit. The **SG Tools** tab appears on the ribbon.

## How these tools are made

I plan each tool and decide how it should behave, the code is written with an AI assistant (Claude), and I don't move on until I can explain what every part does. Each tool goes through the same steps: plan, research, outline, code, explain, polish, stress-test, ship. The steps are adapted from Erik Frits's PROCESS framework for pyRevit tools.
