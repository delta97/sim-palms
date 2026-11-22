"""One module per ``palmfx`` subcommand, discovered by :mod:`palmfx.offline.cli`.

Contract: a module in this package exposes ``register(subparsers)``, where ``subparsers`` is the
object returned by ``ArgumentParser.add_subparsers``. ``register`` adds one or more subcommand
parsers and gives each a ``func`` default (``parser.set_defaults(func=...)``); ``func`` takes the
parsed ``argparse.Namespace`` and returns the process exit code.

Every command takes ``--session data/fx/<session_id>``. Call
``palmfx.offline.cli.add_standard_args(parser)`` to get ``--session`` plus the shared palmfix
flags (``-v``, ``-q``, ``--data-dir``, ``--log-file``, ...), and
``palmfx.offline.cli.session_from_args(args)`` to open the session. Raise ``palmcore.errors``
exceptions for expected failures; the shared runner maps them to exit codes.

A module without ``register`` is skipped with a warning. Adding a file here is all it takes to add
a command; no shared file needs editing.
"""
