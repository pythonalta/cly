import argparse
import inspect
import sys


class CLI:
    def __init__(self, name="cli", desc=""):
        self._parser = argparse.ArgumentParser(prog=name, description=desc)
        self._commands = {}
        self._options = {}

    def _add_arguments_from_signature(self, parser, func):
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            help_text = f"Argument for '{name}'"

            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD or param.kind == inspect.Parameter.POSITIONAL_ONLY:
                if param.default is inspect.Parameter.empty:
                    parser.add_argument(name, help=help_text)
                else:
                    parser.add_argument(f"--{name}", help=help_text, default=param.default)

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.default is inspect.Parameter.empty:
                    parser.add_argument(f"--{name}", required=True, help=help_text)
                else:
                    parser.add_argument(f"--{name}", default=param.default, help=help_text)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                parser.add_argument(name, nargs='*', help=f"Variable positional arguments for '{name}'")
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                raise TypeError(f"**kwargs parameter ('{name}') is not supported in CLI arguments.")

    def cmd(self, name, help=None):
        def decorator(func):
            if name in self._commands:
                raise ValueError(f"Command '{name}' already registered.")
            if not hasattr(self, '_command_subparsers'):
                self._command_subparsers = self._parser.add_subparsers(title="Available commands", dest="command")

            cmd_parser = self._command_subparsers.add_parser(name, help=help or func.__doc__)

            try:
                self._add_arguments_from_signature(cmd_parser, func)
            except TypeError as e:
                raise TypeError(f"Error adding arguments for command '{name}': {e}")

            self._commands[name] = {
                "func": func,
                "parser": cmd_parser,
                "subcommands_parser": None
            }
            cmd_parser.set_defaults(func=func, command_name=name, is_subcommand=False)
            return func
        return decorator

    def opt(self, short=None, long=None, help=None):
        def decorator(func):
            option_names = []
            if short:
                option_names.append(short)
                if short in self._options:
                    raise ValueError(f"Option '{short}' already registered.")
            if long:
                option_names.append(long)
                if long in self._options:
                    raise ValueError(f"Option '{long}' already registered.")
            if not option_names:
                raise ValueError("At least 'short' or 'long' must be provided for an option.")

            sig = inspect.signature(func)
            nargs = None
            action = 'store'
            option_arg_names = []

            for name, param in sig.parameters.items():
                option_arg_names.append(name)
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    nargs = '*'
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    raise TypeError(f"**kwargs parameter ('{name}') is not supported for option arguments.")
            self._parser.add_argument(
                *option_names,
                help=help or func.__doc__,
                nargs=nargs, action=argparse.Append if nargs is not None else 'store',
                dest="_opt_args"
                )
            self._options[tuple(option_names)] = {
                "func": func,
                "arg_names": option_arg_names
            }
            return func
        return decorator

    def subcmd(self, name, cmd, help=None):
        def decorator(func):
            if cmd not in self._commands:
                raise ValueError(f"Main command '{cmd}' not registered yet.")
            main_command_info = self._commands[cmd]
            if main_command_info["subcommands_parser"] is None:
                main_command_info["subcommands_parser"] = main_command_info["parser"].add_subparsers(
                    title=f"Commands for '{cmd}'",
                    dest="subcommand",
                    help=f"Specific commands under '{cmd}'"
                )
                if 'func' in main_command_info["parser"]._defaults:
                    del main_command_info["parser"]._defaults['func']
                    del main_command_info["parser"]._defaults['command_name']
                    del main_command_info["parser"]._defaults['is_subcommand']
            subparser = main_command_info["subcommands_parser"].add_parser(name, help=help or func.__doc__)
            try:
                self._add_arguments_from_signature(subparser, func)
            except TypeError as e:
                raise TypeError(f"Error adding arguments for subcommand '{name}' under '{cmd}': {e}") from e
            self._commands[(cmd, name)] = {"func": func, "parser": subparser}
            subparser.set_defaults(func=func, command_name=cmd, subcommand_name=name, is_subcommand=True)
            return func
        return decorator

    def exec(self, args=None):
        if sys.version_info >= (3, 7):
            if hasattr(self, '_command_subparsers'):
                self._command_subparsers.required = True
            for main_cmd_info in self._commands.values():
                if isinstance(main_cmd_info, dict) and main_cmd_info.get("subcommands_parser"):
                    main_cmd_info["subcommands_parser"].required = True
        parsed_args = self._parser.parse_args(args)
        if hasattr(parsed_args, '_opt_args'):
            pass
        if hasattr(parsed_args, 'func'):
            target_func = parsed_args.func
            target_sig = inspect.signature(target_func)
            call_args = []
            call_kwargs = {}
            remaining_args = []
            for name, param in target_sig.parameters.items():
                if hasattr(parsed_args, name):
                    value = getattr(parsed_args, name)

                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        if isinstance(value, (list, tuple)):
                            call_args.extend(value)
                        elif value is not None:
                            call_args.append(value)
                    elif param.kind == inspect.Parameter.VAR_KEYWORD:
                        pass
                    else:
                        call_kwargs[name] = value
            try:
                target_func(*call_args, **call_kwargs)
            except TypeError as e:
                print(f"Error calling function '{target_func.__name__}': {e}", file=sys.stderr)
                print("Parsed arguments:", parsed_args, file=sys.stderr)
                print("Signature:", target_sig, file=sys.stderr)
                print("Attempted call args:", call_args, file=sys.stderr)
                print("Attempted call kwargs:", call_kwargs, file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print("An error occurred during function execution:", e, file=sys.stderr)
                sys.exit(1)
        else:
            self._parser.print_help()


