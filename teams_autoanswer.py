#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-contestar Microsoft Teams en macOS (RPA en Python)
- Detecta llamada por Accesibilidad (AX) y pulsa el botón Aceptar (AXPress)
- Si no aparece el botón, trae Teams al frente y manda Cmd+Shift+A en ráfaga
Requisitos:
  pip install pyobjc pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
Permisos: Terminal (o iTerm) en Accesibilidad + Monitoreo de entrada
"""

import time
import subprocess
from typing import Optional, Tuple

from Quartz import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXDescriptionAttribute,
    kAXValueAttribute,
    kAXIdentifierAttribute,
    kAXHelpAttribute,
    kAXPressAction,
)
from Quartz import CoreGraphics as CG
from AppKit import NSWorkspace

# ---------- Config ----------
POLL_SECONDS = 0.35
COOLDOWN_SEC = 7
FOCUS_DELAY  = 0.28
BURST_SIZE   = 6
PULSE_DELAY  = 0.06

TEAMS_BUNDLE_IDS = ["com.microsoft.teams2", "com.microsoft.teams"]
TEAMS_APP_NAMES  = ["Microsoft Teams", "Microsoft Teams (work or school)", "Microsoft Teams classic", "Teams"]

ACCEPT_LABELS = [
    "Aceptar con audio","Aceptar con video","Aceptar","Contestar","Responder","Aceptar llamada",
    "Accept with audio","Accept with video","Accept","Answer","Answer with audio","Answer with video",
    "Aceitar","Aceitar com áudio","Aceitar com vídeo"
]
DECLINE_LABELS = ["Rechazar","Decline","Reject","Cancelar","Cancel","Recusar","Rejeitar"]
CALL_HINTS     = ["Llamada","Llamada entrante","Incoming call","Calling","Ring","Entrante","Chamada"]

# ---------- Utils ----------
def now() -> float: return time.time()

def get_teams_pid() -> Optional[int]:
    ws = NSWorkspace.sharedWorkspace()
    for app in ws.runningApplications():
        bid = app.bundleIdentifier()
        name = app.localizedName()
        if (bid and bid in TEAMS_BUNDLE_IDS) or (name and name in TEAMS_APP_NAMES):
            return app.processIdentifier()
    return None
cler
def bring_teams_to_front():
    osa = r'''
    on run
      tell application "System Events"
        set tapps to {"Microsoft Teams", "Microsoft Teams (work or school)", "Microsoft Teams classic", "Teams"}
        repeat with aname in tapps
          if exists application process (aname as text) then
            tell application (aname as text) to activate
            tell application process (aname as text)
              set visible to true
              try
                repeat with w in windows
                  try
                    if value of attribute "AXMinimized" of w is true then
                      set value of attribute "AXMinimized" of w to false
                    end if
                  end try
                end repeat
              end try
            end tell
            exit repeat
          end if
        end repeat
      end tell
    end run
    '''
    subprocess.run(["osascript", "-e", osa], capture_output=True)
    time.sleep(FOCUS_DELAY)

# ---- Teclas Cmd+Shift+A con Quartz ----
KC_A = 0x00  # keycode 'a' layout US (suele valer en macOS)

def key_event(down: bool, keycode: int, flags: int):
    ev = CG.CGEventCreateKeyboardEvent(None, keycode, down)
    CG.CGEventSetFlags(ev, flags)
    CG.CGEventPost(CG.kCGHIDEventTap, ev)

def send_cmd_shift_a_burst():
    flags = CG.kCGEventFlagMaskCommand | CG.kCGEventFlagMaskShift
    for _ in range(BURST_SIZE):
        key_event(True,  KC_A, flags)
        time.sleep(0.012)
        key_event(False, KC_A, flags)
        time.sleep(PULSE_DELAY)

# ---------- Accesibilidad (AX) ----------
def _ax_attr(elem, attr):
    ok, val = AXUIElementCopyAttributeValue(elem, attr, None)
    return val if ok == 0 else None

def _ax_children(elem):
    kids = _ax_attr(elem, kAXChildrenAttribute)
    return kids or []

def _ax_role(elem) -> str:
    r = _ax_attr(elem, kAXRoleAttribute)
    return r or ""

def _ax_fields(elem):
    return [
        _ax_attr(elem, kAXTitleAttribute),
        _ax_attr(elem, kAXDescriptionAttribute),
        _ax_attr(elem, kAXValueAttribute),
        _ax_attr(elem, kAXIdentifierAttribute),
        _ax_attr(elem, kAXHelpAttribute),
    ]

def _any_match(strings, fields) -> bool:
    for s in strings:
        s_low = (s or "").lower()
        for f in fields:
            if isinstance(f, str) and s_low in f.lower():
                return True
    return False

def _is_accept(elem) -> bool:
    return _any_match(ACCEPT_LABELS, _ax_fields(elem))

def _looks_like_incoming(elem) -> bool:
    fs = _ax_fields(elem)
    return _any_match(CALL_HINTS, fs) or _any_match(DECLINE_LABELS, fs)

def ax_find_accept_or_incoming(ax_app, max_depth=9) -> Tuple[object, bool]:
    """Devuelve (btn_aceptar | None, incoming_bool)."""
    def walk(node, depth):
        if not node or depth > max_depth:
            return None, False
        role = _ax_role(node)
        incoming_here = False
        if role in ("AXButton","AXStaticText","AXGroup","AXSheet","AXWindow","AXToolbar"):
            if _is_accept(node):
                return node, True
            if _looks_like_incoming(node):
                incoming_here = True
        for k in _ax_children(node):
            btn, inc = walk(k, depth+1)
            if btn:
                return btn, True
            if inc:
                incoming_here = True
        return None, incoming_here
    return walk(ax_app, 1)

def ax_press(elem) -> bool:
    try:
        res = AXUIElementPerformAction(elem, kAXPressAction)
        return res == 0
    except Exception:
        return False

# ---------- Loop principal ----------
def main():
    print("[py-autoanswer] Iniciado. Poll=%.2fs Cooldown=%ds Focus=%.2fs Burst=%d x %.2fs" %
          (POLL_SECONDS, COOLDOWN_SEC, FOCUS_DELAY, BURST_SIZE, PULSE_DELAY))
    last_fire = 0.0

    while True:
        t0 = now()
        if (t0 - last_fire) >= COOLDOWN_SEC:
            pid = get_teams_pid()
            if pid:
                ax_app = AXUIElementCreateApplication(pid)
                btn, incoming = ax_find_accept_or_incoming(ax_app, max_depth=9)
                if incoming:
                    if btn:
                        print("[py-autoanswer] Llamada detectada (AX). AXPress…")
                        if ax_press(btn):
                            print("[py-autoanswer] AXPress OK")
                            last_fire = now()
                        else:
                            print("[py-autoanswer] AXPress falló → fallback Cmd+Shift+A")
                            bring_teams_to_front()
                            send_cmd_shift_a_burst()
                            last_fire = now()
                    else:
                        print("[py-autoanswer] Llamada detectada (AX sin botón). Fallback Cmd+Shift+A")
                        bring_teams_to_front()
                        send_cmd_shift_a_burst()
                        last_fire = now()
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[py-autoanswer] Salido por usuario")
