import argparse
import inspect
import sys
import os

class CLI:
    def __init__(self, name="cli", desc=""):
        self._parser = argparse.ArgumentParser(prog=name, description=desc)
        self._commands = {}
        self._options = {}
        self._command_subparsers = None

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

            if not hasattr(self, '_command_subparsers') or self._command_subparsers is None:
                self._command_subparsers = self._parser.add_subparsers(title="Available commands", dest="command", help="Available commands")

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
                action = 'store_true' if all(not opt.startswith('-') for opt in option_names) else 'store_const'
                const = True
            elif nargs is None:
                nargs = 1
                action = 'store'
            else:
                action = 'store'

            dest_name = option_names[0].lstrip('-').replace('-', '_')

            self._parser.add_argument(
                *option_names,
                help=help or func.__doc__,
                nargs=nargs,
                action=action,
                dest=dest_name,
            )

            self._options[tuple(option_names)] = {
                "func": func,
                "arg_names": option_arg_names,
                "dest": dest_name
            }
            return func
        return decorator


    def subcmd(self, name, cmd_path, help=None):
        def decorator(func):
            cmd_path_list = cmd_path.split()
            current_commands_dict = self._commands
            parent_parser = self._parser

            for i, current_cmd_name in enumerate(cmd_path_list):
                if current_cmd_name not in current_commands_dict:
                    raise ValueError(f"Parent command/subcommand '{' '.join(cmd_path_list[:i+1])}' not registered yet.")

                cmd_info = current_commands_dict[current_cmd_name]
                parent_parser = cmd_info["parser"]

                if i < len(cmd_path_list) - 1:
                    if cmd_info.get("subcommands_parser") is None:
                        cmd_info["subcommands_parser"] = parent_parser.add_subparsers(
                            title=f"Commands for '{' '.join(cmd_path_list[:i+2])}'",
                            dest="_".join(cmd_path_list[:i+2]) + "_subcommand",
                            help=f"Specific commands under '{' '.join(cmd_path_list[:i+1])}'"
                        )
                        for default_key in ['func', 'command_name', 'subcommand_name', 'is_subcommand']:
                            if default_key in parent_parser._defaults:
                                del parent_parser._defaults[default_key]

                    current_commands_dict = current_commands_dict[(current_cmd_name,)]

            parent_command_name = cmd_path_list[-1]
            parent_info = current_commands_dict[parent_command_name]

            if parent_info.get("subcommands_parser") is None:
                parent_info["subcommands_parser"] = parent_info["parser"].add_subparsers(
                    title=f"Commands for '{cmd_path}'",
                    dest="_".join(cmd_path_list) + "_subcommand",
                    help=f"Specific commands under '{cmd_path}'"
                )
                for default_key in ['func', 'command_name', 'subcommand_name', 'is_subcommand']:
                    if default_key in parent_info["parser"]._defaults:
                        del parent_info["parser"]._defaults[default_key]

            subparser = parent_info["subcommands_parser"].add_parser(name, help=help or func.__doc__)

            try:
                self._add_arguments_from_signature(subparser, func)
            except TypeError as e:
                raise TypeError(f"Error adding arguments for subcommand '{name}' under '{cmd_path}': {e}") from e

            subcommand_key = tuple(cmd_path_list + [name])
            self._commands[subcommand_key] = {"func": func, "parser": subparser}
            subparser.set_defaults(func=func, command_path=cmd_path_list, subcommand_name=name, is_subcommand=True)
            return func

        return decorator


    def _generate_bash_completion(self):
        script = f"""
_{self._parser.prog}_completion() {{
    local cur prev commands subcommands
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    commands="{ " ".join([c for c in self._commands if isinstance(c, str)]) }"

    local command_index=-1
    for i in "${{!COMP_WORDS[@]}}"; do
        if [[ $i -gt 0 ]]; then
            local word="${{COMP_WORDS[i]}}"
            if [[ ${{commands}} =~ (^| )"${{word}}"( |$) ]]; then
                command_index=$i
                break
            fi
        fi
    done

    if [[ $command_index -eq -1 ]]; then
        COMPREPLY=( $(compgen -W "${{commands}} --completion" -- ${{cur}}) )
        return 0
    else
        local current_cmd="${{COMP_WORDS[command_index]}}"
        local current_path="${{current_cmd}}"
        local current_commands_dict="${{commands}}"

        local processing_subcommands=true
        local parent_parser_dest="command"

        for ((i=command_index+1; i<COMP_CWORD; i++)); do
            local word="${{COMP_WORDS[i]}}"
            local found_subcommand=false

            if [[ ${{processing_subcommands}} == true ]]; then
                 case "${{current_path}}" in
                    cmd1)
                        subcommands="subcmd1 subcmd_other"
                        ;;
                    *)
                        subcommands=""
                        ;;
                 esac

                if [[ ${{subcommands}} =~ (^| )"${{word}}"( |$) ]]; then
                     current_path="${{current_path}} ${{word}}"
                else
                     processing_subcommands=false
                fi
            fi
        done

        if [[ ${{processing_subcommands}} == true ]]; then
             case "${{current_path}}" in
                cmd1)
                    subcommands="subcmd1 subcmd_other"
                    ;;
                 cmd1\\ subcmd1)
                     subcommands="subsubcmd1"
                     ;;
                *)
                    subcommands=""
                    ;;
             esac
             COMPREPLY=( $(compgen -W "${{subcommands}}" -- ${{cur}}) )
        else
              local options="$(printf '%s\\n' "${{_parser.format_help().splitlines()[@]}}" | grep -oP '^  -\\w(, --[\\w-]+)?' | sed 's/,//g' | awk '{{print $1, $2}}' | xargs echo )"

              local used_options=""
              for word in "${{COMP_WORDS[@]}}"; do
                  if [[ ${{word}} =~ ^- ]]; then
                      used_options+=" ${{word}}"
                  fi
              done
              local available_options=""
              for opt in ${{options}}; do
                  if [[ ! ${{used_options}} =~ (^| )${{opt}}( |$) ]]; then
                      available_options+="${{opt}} "
                  fi
              done

             COMPREPLY=( $(compgen -W "${{available_options}}" -- ${{cur}}) )

        fi
    fi


}}
complete -F _{self._parser.prog}_completion {self._parser.prog}
"""
        return script


    def exec(self, args=None):
        parsed_args, remaining_args = self._parser.parse_known_args(args)

        if hasattr(parsed_args, 'completion') and parsed_args.completion:
            print(self._generate_bash_completion())
            sys.exit(0)

        if sys.version_info >= (3, 7):
            if hasattr(self, '_command_subparsers') and self._command_subparsers:
                self._command_subparsers.required = True
            for key, cmd_info in self._commands.items():
                if isinstance(cmd_info, dict) and cmd_info.get("subcommands_parser"):
                    cmd_info["subcommands_parser"].required = True


        parsed_args = self._parser.parse_args(args)

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
                expected_params = list(target_sig.parameters.keys())
                print(f"Expected parameters: {expected_params}", file=sys.stderr)
                print(f"Provided keyword arguments: {call_kwargs}", file=sys.stderr)
                print(f"Provided positional arguments: {call_args}", file=sys.stderr)
                print("Parsed arguments namespace:", vars(parsed_args), file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print("An error occurred during function execution:", e, file=sys.stderr)
                sys.exit(1)

        else:
            self._parser.print_help()

