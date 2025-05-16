import sys
import inspect
import argparse

class CLIGroup:
    def __init__(self, name="group", desc=""):
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

class CLI:
    def __init__(self, name="cli", desc=""):
        self._parent_cmds = {}
        self._sub_cmds = {}
        self._help = desc
        self._prog = name
        self._signatures = {}
        self._completions = {}

    def include_group(self, group: CLIGroup, prefix: str = ""):
        prefix = prefix.strip('/')
        for parent_cmd_name, parent_func in group._parent_cmds.items():
            new_cmd_name = '/'.join(filter(None, [prefix, parent_cmd_name]))
            parts = new_cmd_name.split('/')
            if len(parts) == 1:
                self._parent_cmds[parts[0]] = parent_func
                self._sub_cmds.setdefault(parts[0], {})
                self._signatures[parts[0]] = group._signatures[parent_cmd_name]
            elif len(parts) == 2:
                p, s = parts
                self._sub_cmds.setdefault(p, {})
                self._sub_cmds[p][s] = parent_func
            else:
                raise Exception("Max nesting 2 supported")
            if (parent_cmd_name,) in group._completions:
                self._completions[tuple(parts)] = group._completions[(parent_cmd_name,)]

        for parent, subcmds in group._sub_cmds.items():
            for sub_name, func in subcmds.items():
                full_cmd_path = '/'.join(filter(None, [prefix, parent, sub_name]))
                parts = full_cmd_path.split('/')
                if len(parts) == 2:
                    main, sub = parts
                    self._sub_cmds.setdefault(main, {})
                    self._sub_cmds[main][sub] = func
                else:
                    raise Exception("Max nesting 2 supported")
                if (parent, sub_name) in group._completions:
                    self._completions[tuple(parts)] = group._completions[(parent, sub_name)]

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

    def include_group(self, group: CLIGroup, prefix: str = ""):
        prefix = prefix.strip('/')
        for parent_cmd_name, parent_func in group._parent_cmds.items():
            new_cmd_name = '/'.join(filter(None, [prefix, parent_cmd_name]))
            parts = new_cmd_name.split('/')
            if len(parts) == 1:
                self._parent_cmds[parts[0]] = parent_func
                self._sub_cmds.setdefault(parts[0], {})
                self._signatures[parts[0]] = group._signatures[parent_cmd_name]
            elif len(parts) == 2:
                p, s = parts
                self._sub_cmds.setdefault(p, {})
                self._sub_cmds[p][s] = parent_func
            else:
                raise Exception("Max nesting 2 supported")
            if (parent_cmd_name,) in group._completions:
                self._completions[tuple(parts)] = group._completions[(parent_cmd_name,)]

        for parent, subcmds in group._sub_cmds.items():
            for sub_name, func in subcmds.items():
                full_cmd_path = '/'.join(filter(None, [prefix, parent, sub_name]))
                parts = full_cmd_path.split('/')
                if len(parts) == 2:
                    main, sub = parts
                    self._sub_cmds.setdefault(main, {})
                    self._sub_cmds[main][sub] = func
                else:
                    raise Exception("Max nesting 2 supported")
                if (parent, sub_name) in group._completions:
                    self._completions[tuple(parts)] = group._completions[(parent, sub_name)]

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
        real_roots = set(self._parent_cmds.keys())
        cmds = sorted(real_roots)
        subcmds_map = {parent: sorted([sub for sub in subs if sub]) for parent, subs in self._sub_cmds.items()}

        opt_map = {}
        val_map = {}

        for cmd, sig in self._signatures.items():
            label = cmd
            opt_map.setdefault(label, [])
            for p in sig.parameters.values():
                opt = f"--{p.name}"
                if opt not in opt_map[label]:
                    opt_map[label].append(opt)

        for cmdpath, comp in self._completions.items():
            label = "_".join(cmdpath)
            opt_map.setdefault(label, [])
            val_map.setdefault(label, {})
            for arg, vals in comp.items():
                if f"--{arg}" not in opt_map[label]:
                    opt_map[label].append(f"--{arg}")
                val_map[label][arg] = vals

        arrays = []
        for label, argvals in val_map.items():
            for arg, vals in argvals.items():
                basharr = f"_COMP_{label}__{arg}"
                valstr = " ".join([f'"{v}"' for v in vals])
                arrays.append(f'{basharr}=({valstr})')

        script = [
            "#!/bin/bash",
            *arrays,
            "",
            f'_{self._prog}_completion() {{',
            '    local cur prev words cword',
            '    COMPREPLY=()',
            '    cur="${COMP_WORDS[COMP_CWORD]}"',
            '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
            '    words=("${COMP_WORDS[@]}")',
            '    cword=$COMP_CWORD',
            '',
            f'    cmds="{ " ".join(cmds) }"',
            '',
            '    declare -A subcmds',
        ]
        for parent, subs in subcmds_map.items():
            script.append(f'    subcmds["{parent}"]="{ " ".join(subs) }"')
        script.append('    declare -A opts')
        for label, optlist in opt_map.items():
            script.append(f'    opts["{label}"]="{ " ".join(optlist) }"')

        script.extend([
            '    if [[ $cword -eq 1 ]]; then',
            '        COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )',
            '        return 0',
            '    fi',
            '',
            '    local command1="${words[1]}"',
            '    local subcmd=""',
            '    local label="$command1"',
            '',
            '    if [[ $cword -ge 3 ]]; then',
            '        if [[ -n "${subcmds[$command1]}" ]]; then',
            '            for candidate in ${subcmds[$command1]}; do',
            '                if [[ "$candidate" == "${words[2]}" ]]; then',
            '                    subcmd="$candidate"',
            '                    label="${command1}_$candidate"',
            '                    break',
            '                fi',
            '            done',
            '        fi',
            '    fi',
            '',
            '    if [[ $cword -eq 2 ]]; then',
            '        if [[ -n "${subcmds[$command1]}" ]]; then',
            '            COMPREPLY+=( $(compgen -W "${subcmds[$command1]}" -- "$cur") )',
            '        fi',
            '        if [[ -n "${opts[$command1]}" ]]; then',
            '            COMPREPLY+=( $(compgen -W "${opts[$command1]}" -- "$cur") )',
            '        fi',
            '        return 0',
            '    fi',
            '',
            '    if [[ $subcmd != "" && $cword -eq 3 ]]; then',
            '        if [[ -n "${opts[$label]}" ]]; then',
            '            COMPREPLY=( $(compgen -W "${opts[$label]}" -- "$cur") )',
            '            return 0',
            '        fi',
            '    fi',
            '',
            '    if [[ "$prev" == --* ]]; then',
            '        argname="${prev#--}"',
            '        arrvar="_COMP_${label//[^a-zA-Z0-9_]/_}__${argname}"',
            '        if declare -p $arrvar &>/dev/null; then',
            '            # eval the array by name, output all elements as words',
            r'            COMPREPLY=( $(compgen -W "$(eval "echo \${${arrvar}[@]}")" -- "$cur") )',
            '            return 0',
            '        fi',
            '    elif [[ "$cur" == --*=* ]]; then',
            '        argname="${cur%%=*}"',
            '        argname="${argname#--}"',
            '        arrvar="_COMP_${label//[^a-zA-Z0-9_]/_}__${argname}"',
            '        if declare -p $arrvar &>/dev/null; then',
            r'            COMPREPLY=( $(compgen -W "$(eval "echo \${${arrvar}[@]}")" -- "") )',
            '            return 0',
            '        fi',
            '    fi',
            '    return 0',
            '}',
            f'complete -F _{self._prog}_completion {self._prog}'
        ])
        print('\n'.join(script))
