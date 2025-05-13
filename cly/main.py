import argparse
import inspect
import sys


class CLI:
    def __init__(self, name="cli", desc=""):
        self._parser = argparse.ArgumentParser(prog=name, description=desc)
        self._subparsers = self._parser.add_subparsers(title="Available commands", dest="command")
        self._commands = {}
        self._subcommands = {}

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

    def option(self, name, desc=None):
        def decorator(func):
            if name in self._commands:
                raise ValueError(f"Command '{name}' already registered.")

            parser = self._subparsers.add_parser(name, help=desc or func.__doc__)
            try:
                self._add_arguments_from_signature(parser, func)
            except TypeError as e:
                raise TypeError(f"Error adding arguments for command '{name}': {e}")
            self._commands[name] = {
                "func": func,
                "parser": parser,
                "subcommands_parser": None
            }
            parser.set_defaults(func=func, command_name=name, is_subcommand=False)
            return func
        return decorator

    def suboption(self, name, option, desc=None):
        def decorator(func):
            if option not in self._commands:
                raise ValueError(f"Main command '{option}' not registered yet.")

            main_command_info = self._commands[option]

            if main_command_info["subcommands_parser"] is None:
                main_command_info["subcommands_parser"] = main_command_info["parser"].add_subparsers(
                    title=f"Commands for '{option}'",
                    dest="subcommand",
                    help=f"Specific commands under '{option}'"
                )
                if 'func' in main_command_info["parser"]._defaults:
                    del main_command_info["parser"]._defaults['func']
                    del main_command_info["parser"]._defaults['command_name']
                    del main_command_info["parser"]._defaults['is_subcommand']

            subparser = main_command_info["subcommands_parser"].add_parser(name, help=desc or func.__doc__)

            try:
                self._add_arguments_from_signature(subparser, func)
            except TypeError as e:
                raise TypeError(f"Error adding arguments for subcommand '{name}' under '{option}': {e}") from e

            if option not in self._subcommands:
                self._subcommands[option] = {}
            if name in self._subcommands[option]:
                raise ValueError(f"Subcommand '{name}' under '{option}' already registered.")

            self._subcommands[option][name] = {"func": func, "parser": subparser}
            subparser.set_defaults(func=func, command_name=option, subcommand_name=name, is_subcommand=True)
            return func

        return decorator

    def parse_and_execute(self, args=None):
        if sys.version_info >= (3, 7):
            if self._subparsers:
                self._subparsers.required = True
            for main_cmd_info in self._commands.values():
                if main_cmd_info["subcommands_parser"]:
                    main_cmd_info["subcommands_parser"].required = True
        parsed_args = self._parser.parse_args(args)

        if hasattr(parsed_args, 'func'):
            target_func = parsed_args.func
            target_sig = inspect.signature(target_func)
            call_args = {}
            call_kwargs = {}

            for name, param in target_sig.parameters.items():
                if hasattr(parsed_args, name):
                    value = getattr(parsed_args, name)

                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        call_args.update({name: value})
                        call_args_list = value

                    elif param.kind == inspect.Parameter.VAR_KEYWORD:
                        pass
                    else:
                        call_kwargs[name] = value
            try:
                final_args_tuple = tuple(call_args_list) if 'call_args_list' in locals() else ()
                target_func(*final_args_tuple, **call_kwargs)

            except TypeError as e:
                print(f"Error calling command function '{target_func.__name__}': {e}", file=sys.stderr)
                print("Parsed arguments:", parsed_args, file=sys.stderr)
                print("Signature:", target_sig, file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print("An error occurred during command execution:", e, file=sys.stderr)
                sys.exit(1)

        else:
            self._parser.print_help()
