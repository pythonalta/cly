import sys
import inspect
import argparse

class CLI:
    def __init__(self, name="cli", desc=""):
        self._parent_cmds = {}
        self._sub_cmds = {}
        self._help = desc
        self._prog = name
        self._signatures = {}
        self._completions = {}

    def cmd(self, path, help=None, completion=None):
        parts = path.strip('/').split('/')
        tuple_path = tuple(parts)
        if completion is not None:
            self._completions[tuple_path] = completion
        if len(parts) == 1:
            name = parts[0]
            def decorator(func):
                self._parent_cmds[name] = func
                self._sub_cmds.setdefault(name, {})
                self._signatures[name] = inspect.signature(func)
                return func
            return decorator
        elif len(parts) == 2:
            parent, sub = parts
            def decorator(func):
                self._sub_cmds.setdefault(parent, {})
                self._sub_cmds[parent][sub] = func
                return func
            return decorator
        else:
            raise Exception("Max nesting 2 supported")

    def exec(self, args=None):
        argv = sys.argv[1:] if args is None else args
        if '--completion' in argv:
            self.print_completion()
            sys.exit(0)

        if not argv:
            self.show_help()
            sys.exit(1)

        cmd = argv[0]
        if cmd not in self._parent_cmds:
            print(f"Unknown command '{cmd}'.")
            self.show_help()
            sys.exit(1)

        subcmds = self._sub_cmds.get(cmd, {})
        parent_func = self._parent_cmds[cmd]
        sig = self._signatures[cmd]
        params = list(sig.parameters.values())

        next_arg = argv[1] if len(argv) > 1 else None
        if next_arg is not None and next_arg in subcmds:
            func = subcmds[next_arg]
            func()
            return

        ap = argparse.ArgumentParser(prog=f"{self._prog} {cmd}", add_help=False)
        param_names = []
        for p in params:
            ap.add_argument(f"--{p.name}", dest="op_" + p.name, required=False)
            ap.add_argument(p.name, nargs='?', default=None)
            param_names.append(p.name)

        ns, _ = ap.parse_known_args(argv[1:])

        kw = {}
        for p in params:
            opt_val = getattr(ns, "op_" + p.name)
            pos_val = getattr(ns, p.name)
            val = opt_val if opt_val is not None else pos_val
            if val is None and p.default != inspect.Parameter.empty:
                val = p.default
            if val is None:
                print(f"Missing required argument: {p.name}")
                sys.exit(1)
            kw[p.name] = val

        parent_func(**kw)

    def show_help(self):
        print(f"usage: {self._prog} <command> [<args>]")
        print(f"Available commands: {', '.join(self._parent_cmds.keys())}")
        for cmd in self._parent_cmds:
            if self._sub_cmds.get(cmd):
                print(f"  {cmd}: subcommands: {', '.join(self._sub_cmds[cmd].keys())}")

    def print_completion(self):
        commands = list(self._parent_cmds.keys())
        subcmds = self._sub_cmds
        prog = self._prog
        completions = self._completions

        subcompletions = []
        for cmd in commands:
            if subcmds.get(cmd):
                for sc in subcmds[cmd]:
                    subcompletions.append(f"{cmd}:{sc}")

        argcomp_lines = []
        for cmdpath, compdict in completions.items():
            cmdlabel = '_'.join(cmdpath)
            for arg, choices in compdict.items():
                arrname = f"_COMP_{cmdlabel}_{arg}"
                quoted = " ".join(f'"{c}"' for c in choices)
                argcomp_lines.append(f'{arrname}=({quoted})')

        script = [
            "#!/bin/bash",
            "# Portable completion for your CLI",
            *argcomp_lines,
            "",
            f'_{prog}_completion() {{',
            '    local cur prev cmd subcmd',
            '    COMPREPLY=()',
            '    cur="${COMP_WORDS[COMP_CWORD]}"',
            '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
            '    cmd="${COMP_WORDS[1]}"',
            '    subcmd=""',
            '',
            '    # Top-level commands',
            f'    local cmds="{ " ".join(commands) }"',
            f'    local subcmds="{ " ".join(subcompletions) }"',
            '',
            '    if [[ $COMP_CWORD -eq 1 ]]; then',
            '        COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )',
            '        return 0',
            '    fi',
            '',
            '    # Subcommand completion',
            '    if [[ $COMP_CWORD -eq 2 ]]; then',
            '        local subs=""',
            '        for sc in $subcmds; do',
            '            local p="${sc%%:*}"',
            '            local s="${sc##*:}"',
            '            if [[ "$p" == "$cmd" ]]; then',
            '                subs="$subs $s"',
            '            fi',
            '        done',
            '        if [[ -n $subs ]]; then',
            '            COMPREPLY=( $(compgen -W "$subs" -- "$cur") )',
            '            return 0',
            '        fi',
            '    fi',
            '',
            '    # Detect subcmd if present',
            '    if [[ $COMP_CWORD -ge 3 ]]; then',
            '        local maybe_sc="${COMP_WORDS[2]}"',
            '        for sc in $subcmds; do',
            '            local p="${sc%%:*}"',
            '            local s="${sc##*:}"',
            '            if [[ "$p" == "$cmd" && "$s" == "$maybe_sc" ]]; then',
            '                subcmd="$s"',
            '                break',
            '            fi',
            '        done',
            '    fi',
            "",
            "    # Per-argument custom completions",
            '    local clabel="$cmd"',
            '    if [[ -n "$subcmd" ]]; then',
            '        clabel="${clabel}_$subcmd"',
            '    fi',
            "",
            "    case $clabel in"
        ]
        for cmdpath, compdict in completions.items():
            clabel = '_'.join(cmdpath)
            script.append(f"        {clabel})")
            for arg, choices in compdict.items():
                arr_name = f"_COMP_{clabel}_{arg}"
                script += [
                    f'            if [[ "$prev" == "--{arg}" || "$cur" == "{arg}="* ]]; then',
                    f'                COMPREPLY=( $(compgen -W "${{{arr_name}[@]}}" -- "$cur") )',
                    f'                return 0',
                    f'            fi',
                    f'            # positional argument completion:',
                    f'            for ((i=1; i<$COMP_CWORD; i++)); do',
                    f'                if [[ "${{COMP_WORDS[i]}}" == "{cmdpath[-1]}" ]]; then',
                    f'                    local nexti=$((i+1))',
                    f'                    if [[ $COMP_CWORD -eq $nexti ]]; then',
                    f'                        COMPREPLY=( $(compgen -W "${{{arr_name}[@]}}" -- "$cur") )',
                    f'                        return 0',
                    f'                    fi',
                    f'                fi',
                    f'            done'
                ]
            script.append("            ;;")
        script += [
            "    esac",
            "}",
            f'complete -F _{prog}_completion {prog}'
        ]
        print('\n'.join(script))
