"""Send physical cut outlines to the local Epilog Dashboard print queue."""
from __future__ import annotations

import ctypes as ct
from ctypes import wintypes as wt
import math
import sys

from app.geometry.cut_square import CutSquare


PRINTER_NAME = "Epilog Engraver"
_CUSTOM_POSTSCRIPT_FORM = 32767
_DM_OUT_BUFFER = 2
_DM_IN_BUFFER = 8
# DocumentProperties validates the public fields alongside the driver's private
# data. This prefix has the same layout as DEVMODEW through dmPaperWidth.
class _PageSettings(ct.Structure):
    _fields_ = [
        ("device_name", wt.WCHAR * 32),
        ("spec_version", wt.WORD), ("driver_version", wt.WORD),
        ("size", wt.WORD), ("driver_extra", wt.WORD),
        ("fields", wt.DWORD), ("orientation", ct.c_short),
        ("paper_size", ct.c_short), ("paper_length", ct.c_short),
        ("paper_width", ct.c_short),
    ]


class _DocInfo(ct.Structure):
    _fields_ = [
        ("size", wt.INT), ("name", wt.LPCWSTR), ("output", wt.LPCWSTR),
        ("datatype", wt.LPCWSTR), ("type", wt.DWORD),
    ]


def _api(library, name, result, *args):
    method = getattr(library, name)
    method.argtypes, method.restype = args, result
    return method


def _paper_settings(width: float, height: float) -> tuple[int, int, int]:
    """Windows expects portrait paper dimensions, even for landscape output."""
    if any(not math.isfinite(value) or not 0 < value <= 100 for value in (width, height)):
        raise ValueError("Epilog page dimensions must be positive and at most 100 inches.")
    shorter, longer = sorted((width, height))
    return (2 if width > height else 1), round(longer * 254), round(shorter * 254)


def _outline(cut: CutSquare, dpi_x: int, dpi_y: int, offset_x: int, offset_y: int):
    left, right = (round(x * dpi_x) - offset_x for x in (cut.x, cut.x + cut.width))
    top, bottom = (round(y * dpi_y) - offset_y for y in (cut.y, cut.y + cut.height))
    if left >= right or top >= bottom:
        raise ValueError("A cut is smaller than the resolution of the Epilog driver.")
    return ((left, top), (right, top), (right, bottom), (left, bottom), (left, top))


def _require_local_dashboard_queue():
    if sys.platform != "win32":
        raise OSError("Epilog Dashboard output requires Windows.")
    import winreg

    key = r"SYSTEM\CurrentControlSet\Control\Print\Printers\Epilog Engraver"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as queue:
            port = winreg.QueryValueEx(queue, "Port")[0]
            driver = winreg.QueryValueEx(queue, "Printer Driver")[0]
    except FileNotFoundError as exc:
        raise OSError("Install the Epilog Software Suite to add the Epilog Engraver queue.") from exc
    if port.casefold() != "nul:" or driver.casefold() != "epilog engraver driver":
        raise OSError("The Epilog Engraver queue must use the local Dashboard driver and nul: port.")


def send_to_dashboard(
    title: str, bed_width: float, bed_height: float, cuts: list[CutSquare],
) -> int:
    """Queue one vector page at the exact bed size and return its Windows job ID."""
    orientation, paper_length, paper_width = _paper_settings(bed_width, bed_height)
    if not cuts:
        raise ValueError("Select at least one cut to send to Dashboard.")
    if any(cut.width <= 0 or cut.height <= 0 or
           not cut.is_valid(bed_width, bed_height) for cut in cuts):
        raise ValueError("All Dashboard cuts must have positive dimensions and fit inside the bed.")
    _require_local_dashboard_queue()
    spool = ct.WinDLL("winspool.drv", use_last_error=True)
    gdi = ct.WinDLL("gdi32.dll", use_last_error=True)
    opened = _api(spool, "OpenPrinterW", wt.BOOL, wt.LPWSTR, ct.POINTER(wt.HANDLE), ct.c_void_p)
    close = _api(spool, "ClosePrinter", wt.BOOL, wt.HANDLE)
    properties = _api(spool, "DocumentPropertiesW", wt.LONG, wt.HWND, wt.HANDLE, wt.LPWSTR,
                      ct.c_void_p, ct.c_void_p, wt.DWORD)
    create_dc = _api(gdi, "CreateDCW", wt.HDC, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ct.c_void_p)
    delete_dc = _api(gdi, "DeleteDC", wt.BOOL, wt.HDC)
    handle = wt.HANDLE()
    if not opened(PRINTER_NAME, ct.byref(handle), None):
        raise ct.WinError(ct.get_last_error())
    try:
        size = properties(None, handle, PRINTER_NAME, None, None, 0)
        if size < ct.sizeof(_PageSettings):
            raise OSError("The Epilog driver did not provide page settings.")
        request = ct.create_string_buffer(size)
        if properties(None, handle, PRINTER_NAME, request, None, _DM_OUT_BUFFER) != 1:
            raise OSError("The Epilog driver could not read its page settings.")
        page = _PageSettings.from_buffer(request)
        page.fields |= 0x0F  # DM_ORIENTATION | DM_PAPERSIZE | DM_PAPERLENGTH | DM_PAPERWIDTH
        page.orientation, page.paper_size = orientation, _CUSTOM_POSTSCRIPT_FORM
        page.paper_length, page.paper_width = paper_length, paper_width
        validated = ct.create_string_buffer(size)
        if properties(None, handle, PRINTER_NAME, validated, request,
                      _DM_IN_BUFFER | _DM_OUT_BUFFER) != 1:
            raise OSError("The Epilog driver rejected the selected bed size.")
        dc = create_dc(None, PRINTER_NAME, None, validated)
        if not dc:
            raise ct.WinError(ct.get_last_error())
        try:
            return _render_page(gdi, dc, title, bed_width, bed_height, cuts)
        finally:
            delete_dc(dc)
    finally:
        close(handle)


def _render_page(gdi, dc, title, width, height, cuts):
    caps = _api(gdi, "GetDeviceCaps", ct.c_int, wt.HDC, ct.c_int)
    dpi_x, dpi_y = caps(dc, 88), caps(dc, 90)  # LOGPIXELSX/Y
    if dpi_x <= 0 or dpi_y <= 0:
        raise OSError("The Epilog driver did not report its resolution.")
    page_x, page_y = caps(dc, 110), caps(dc, 111)  # PHYSICALWIDTH/HEIGHT
    # The driver rounds paper to tenths of a millimetre, then to device dots.
    if (abs(page_x - width * dpi_x) > dpi_x * .002 + 1
            or abs(page_y - height * dpi_y) > dpi_y * .002 + 1):
        raise OSError(
            f"Epilog reported {page_x / dpi_x:g} × {page_y / dpi_y:g} in "
            f"for a {width:g} × {height:g} in bed. No job was sent."
        )
    offset_x, offset_y = caps(dc, 112), caps(dc, 113)  # PHYSICALOFFSETX/Y
    outlines = [_outline(cut, dpi_x, dpi_y, offset_x, offset_y) for cut in cuts]
    printable_width, printable_height = caps(dc, 8), caps(dc, 10)  # HORZRES/VERTRES
    if any(x < 0 or y < 0 or x > printable_width or y > printable_height
           for outline in outlines for x, y in outline):
        raise OSError("A cut would be clipped by the Epilog driver's printable area.")

    start_doc = _api(gdi, "StartDocW", ct.c_int, wt.HDC, ct.POINTER(_DocInfo))
    doc = _DocInfo(ct.sizeof(_DocInfo), title, None, None, 0)
    job_id = start_doc(dc, ct.byref(doc))
    if job_id <= 0:
        raise ct.WinError(ct.get_last_error())
    try:
        if _api(gdi, "StartPage", ct.c_int, wt.HDC)(dc) <= 0:
            raise OSError("The Epilog driver could not start the vector page.")
        _draw_outlines(gdi, dc, outlines)
        if _api(gdi, "EndPage", ct.c_int, wt.HDC)(dc) <= 0:
            raise OSError("The Epilog driver could not complete the vector page.")
        if _api(gdi, "EndDoc", ct.c_int, wt.HDC)(dc) <= 0:
            raise OSError("The Epilog driver could not finish the print job.")
    except BaseException:
        _api(gdi, "AbortDoc", ct.c_int, wt.HDC)(dc)
        raise
    return job_id


def _draw_outlines(gdi, dc, outlines):
    make_pen = _api(gdi, "CreatePen", wt.HANDLE, ct.c_int, ct.c_int, wt.DWORD)
    select = _api(gdi, "SelectObject", wt.HANDLE, wt.HDC, wt.HANDLE)
    delete = _api(gdi, "DeleteObject", wt.BOOL, wt.HANDLE)
    move = _api(gdi, "MoveToEx", wt.BOOL, wt.HDC, ct.c_int, ct.c_int, ct.c_void_p)
    line = _api(gdi, "LineTo", wt.BOOL, wt.HDC, ct.c_int, ct.c_int)
    pen = make_pen(0, 1, 255)  # A single device dot, solid RGB red.
    if not pen:
        raise OSError("The Epilog driver could not prepare the vector pen.")
    previous = select(dc, pen)
    try:
        if not previous:
            raise OSError("The Epilog driver could not select the vector pen.")
        for first, *remaining in outlines:
            if not move(dc, *first, None) or not all(line(dc, *point) for point in remaining):
                raise OSError("The Epilog driver could not draw a cut outline.")
    finally:
        if previous:
            select(dc, previous)
        delete(pen)
