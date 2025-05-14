import argparse
import inspect
import sys
import os
import json

class CLI:
    def __init__(self, name="cli", desc=""):
        self._parser = argparse.ArgumentParser(prog=name, description=desc)
        self._commands = {} # Stores a nested structure representing command hierarchy
        self._options = {}
        self._parser.add_argument(
            "--completion",
            action="store_true",
            help="Print bash completion script for the CLI."
        )

    def _add_arguments_from_signature(self, parser, func):
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            help_text = f"Argument for '{name}'"

            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD or param.kind == inspect.Parameter.POSITIONAL_ONLY:
                if param.default is inspect.Parameter.empty:
                    parser.add_argument(name, help=help_text)
                else:
                    parser.add_argument(f"--{name}", help=help_text, default=param.default, required=False)

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.default is inspect.Parameter.empty:
                    parser.add_argument(f"--{name}", required=True, help=help_text)
                else:
                    parser.add_argument(f"--{name}", default=param.default, help=help_text, required=False)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                parser.add_argument(name, nargs='*', help=f"Variable positional arguments for '{name}'")
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                raise TypeError(f"**kwargs parameter ('{name}') is not supported in CLI arguments.")

    def cmd(self, path, help=None):
        def decorator(func):
            command_parts = path.strip("/").split("/")

            current_commands_level = self._commands
            current_parser = self._parser
            full_command_path = []

            for i, part in enumerate(command_parts):
                full_command_path.append(part)
                if len(full_command_path) > 1: # This is a subcommand
                    parent_path = tuple(full_command_path[:-1])
                    if parent_path not in self._commands:
                        raise ValueError(f"Parent command '{'/'.join(parent_path)}' not registered yet.")

                    if not isinstance(current_commands_level.get(part), dict):
                        if current_commands_level.get(part) is not None and not isinstance(current_commands_level.get(part), dict):
                            raise ValueError(f"'{part}' already exists but is not a subcommand parent.")

                        parent_info = self._commands[parent_path]
                        if parent_info.get("subparsers") is None:
                            parent_info["subparsers"] = parent_info["parser"].add_subparsers(
                                title=f"Available subcommands for '{'/'.join(parent_path)}'",
                                dest="_".join(parent_path) + "_subcommand",
                                help=f"Available subcommands under '{'/'.join(parent_path)}'"
                            )

                            for default_key in ['func', 'is_subcommand', 'command_path']:
                                if default_key in parent_info["parser"]._defaults:
                                    del parent_info["parser"]._defaults[default_key]

                        cmd_parser = parent_info["subparsers"].add_parser(part, help=help or func.__doc__)
                        current_commands_level[part] = {"parser": cmd_parser}
                        current_commands_level = current_commands_level[part]
                        current_parser = self._commands[tuple(full_command_path)]["parser"]
                    else:
                        current_commands_level = current_commands_level[part]
                        current_parser = current_commands_level.get("parser")
  
                else: # Top-level command
                    if part in self._commands:
                        raise ValueError(f"Command '{part}' already registered.")

                    if not hasattr(self, '_command_subparsers') or self._command_subparsers is None:
                        self._command_subparsers = self._parser.add_subparsers(title="Available commands", dest="command", help="Available commands")

                    cmd_parser = self._command_subparsers.add_parser(part, help=help or func.__doc__)
                    current_commands_level[part] = {"parser": cmd_parser}
                    current_commands_level = current_commands_level[part]
                    current_parser = cmd_parser

                if tuple(full_command_path) in self._commands and self._commands[tuple(full_command_path)].get("func") is not None:
                    raise ValueError(f"Command '{'/'.join(full_command_path)}' is already a callable command.")

                if i == len(command_parts) - 1:
                    try:
                        self._add_arguments_from_signature(current_parser, func)
                    except TypeError as e:
                        raise TypeError(f"Error adding arguments for command '{path}': {e}") from e

                    self._commands[tuple(full_command_path)] = {"func": func, "parser": current_parser} # Store the func against the full path tuple
                    current_parser.set_defaults(func=func, command_path=full_command_path, is_subcommand=(len(full_command_path) > 1))
                    self._completion_commands[' '.join(full_command_path)] = {}


                else:
                    if isinstance(self._commands.get(tuple(full_command_path)), dict) and self._commands[tuple(full_command_path)].get("func"):
                        raise ValueError(f"Cannot add subcommand '{part}' to command '{'/'.join(full_command_path[:-1])}' because it's already a terminal command.")
        

                if i < len(command_parts) - 1:
                    if tuple(full_command_path) not in self._commands:
                        self._commands[tuple(full_command_path)] = {"parser": current_parser}
                    current_commands_level = self._commands[tuple(full_command_path)]


            return func
        return decorator

    def opt(self, *names, help=None):
        def decorator(func):
            if not names:
                raise ValueError("At least one option name must be provided.")

            for name in names:
                if name in self._options:
                    raise ValueError(f"Option '{name}' already registered.")

            sig = inspect.signature(func)
            nargs = None
            option_arg_names = []

            for name, param in sig.parameters.items():
                option_arg_names.append(name)
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    nargs = '*'
                    break
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    raise TypeError(f"**kwargs parameter ('{name}') is not supported for option arguments.")
                elif param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                    if nargs is None:
                        nargs = 1
                    else:
                        pass

            if len(sig.parameters) == 0:
                nargs = 0
                action = 'store_true' if all(not opt.startswith('-') for opt in names) else 'store_const'
                const = True
            elif nargs is None:
                nargs = 1
                action = 'store'
            else:
                action = 'store'

            dest_name = names[0].lstrip('-').replace('-', '_')

            self._parser.add_argument(
                *names,
                help=help or func.__doc__,
                nargs=nargs,
                action=action,
                dest=dest_name,
            )

            self._options[names] = {
                "func": func,
                "arg_names": option_arg_names,
                "dest": dest_name
            }
            return func
        return decorator

    def exec(self, args=None):
        parsed_args, unknown = self._parser.parse_known_args(args)

        if hasattr(parsed_args, 'completion') and parsed_args.completion:
            bash_completion_script = self._generate_bash_completion()
            print(bash_completion_script)
            sys.exit(0)


        try:
            parsed_args = self._parser.parse_args(args)
        except SystemExit as e:
            sys.exit(e.code)


        if hasattr(parsed_args, 'func'):
            target_func = parsed_args.func
            target_sig = inspect.signature(target_func)
            call_args = []
            call_kwargs = {}

            for name, param in target_sig.parameters.items():
                if hasattr(parsed_args, name):
                    call_kwargs[name] = getattr(parsed_args, name)
                elif param.default is not inspect.Parameter.empty:
                    call_kwargs[name] = param.default
                elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                    call_args.extend(unknown) # Pass unknown arguments as positional args
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    pass
                else:
                     # Handle missing required positional/keyword arguments
                    if param.default is inspect.Parameter.empty:
                        print(f"Error: missing required argument '{name}' for command.", file=sys.stderr)
                        self._parser.print_help(sys.stderr)
                        sys.exit(1)


            # Handle options
            for option_names, option_info in self._options.items():
                dest_name = option_info["dest"]
                if hasattr(parsed_args, dest_name) and getattr(parsed_args, dest_name) is not None:
                    option_func = option_info["func"]
                    option_sig = inspect.signature(option_func)
                    option_call_args = []
                    option_call_kwargs = {}

                    option_value = getattr(parsed_args, dest_name)

                    for i, arg_name in enumerate(option_info["arg_names"]):
                        if option_func.__kwdefaults__ and arg_name in option_func.__kwdefaults__:
                            option_call_kwargs[arg_name] = option_func.__kwdefaults__[arg_name]
                        elif i < len(unknown):
                            option_call_args.append(unknown[i])
                        elif option_sig.parameters[arg_name].default is not inspect.Parameter.empty:
                            option_call_kwargs[arg_name] = option_sig.parameters[arg_name].default
                        else:
                            print(f"Error: missing argument '{arg_name}' for option {'/'.join(option_names)}", file=sys.stderr)
                            sys.exit(1)

                    try:
                        option_func(*option_call_args, **option_call_kwargs)
                    except TypeError as e:
                        print(f"Error calling option function for '{'/'.join(option_names)}': {e}", file=sys.stderr)
                        sys.exit(1)
                    # Remove used arguments from unknown
                    unknown = unknown[len(option_call_args):]


            try:
                target_func(*call_args, **call_kwargs)

                if unknown:
                    print(f"Warning: Unrecognized arguments: {unknown}", file=sys.stderr)

            except TypeError as e:
                print(f"Error calling function '{target_func.__name__}': {e}", file=sys.stderr)
                target_parser = parsed_args.parser if hasattr(parsed_args, 'parser') else self._parser
                target_parser.print_help(sys.stderr)
                sys.exit(1)
            except Exception as e:
                print("An error occurred during function execution:", e, file=sys.stderr)
                sys.exit(1)

        else:
            if hasattr(parsed_args, 'command_path'):
                command_path_str = ' '.join(parsed_args.command_path)
                print(f"Error: Incomplete command. Please specify a subcommand for '{command_path_str}'.", file=sys.stderr)
                target_parser = parsed_args.parser if hasattr(parsed_args, 'parser') else self._parser
                target_parser.print_help(sys.stderr)
            else:
                self._parser.print_help()

