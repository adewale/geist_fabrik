"""Command classes for the GeistFabrik CLI.

This package implements the Command pattern for the CLI, providing:
- BaseCommand: Shared infrastructure for all commands
- Individual command classes: InitCommand, InvokeCommand, etc.

Each command encapsulates its own logic while sharing common functionality
like vault validation, config loading, and error handling through BaseCommand.
"""

from .base import BaseCommand, CommandContext, ExecutionContext, find_vault_root
from .init_cmd import InitCommand
from .invoke_cmd import InvokeCommand
from .stats_cmd import StatsCommand
from .test_all_cmd import TestAllCommand
from .test_cmd import TestCommand
from .validate_cmd import ValidateCommand

__all__ = [
    "BaseCommand",
    "CommandContext",
    "ExecutionContext",
    "InitCommand",
    "InvokeCommand",
    "StatsCommand",
    "TestCommand",
    "TestAllCommand",
    "ValidateCommand",
    "find_vault_root",
]
