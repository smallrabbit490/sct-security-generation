"""Bind the native CLE entry to the build's existing request controls.

The outer runner owns budget freezing, output paths, recovery and worker slots.
This module deliberately exposes no live command until those are implemented.
"""
import sys

from .logical_requests import logical_requests, native
from .task_scope import native_task_scopes


def run_native(execution, arguments, *, entry=None, pending=None, probe=False,
               authorized_target=None):
    previous = sys.argv
    sys.argv = ['native_CLE', *arguments]
    try:
        with execution.physical_records(), native_task_scopes(), logical_requests(
                execution, pending=pending, probe=probe, authorized_target=authorized_target):
            return (entry or native.main)()
    finally:
        sys.argv = previous
