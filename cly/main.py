import sys
import inspect
import argparse

class CommandNode:
    def __init__(self, name=None, help_desc=""):
        self.name = name
        self.help = help_desc
        self.func = None
        self.signature = None
        self.children = dict()
        self.completion = dict()

    def add_child(self, child):
        self.children[child.name] = child

    def get_or_create_child(self, name):
        if name not in self.children:
            self.children[name] = CommandNode(name)
        return self.children[name]

    def find_node(self, argv):
        node = self
        path = []
        idx = 0
        while idx < len(argv):
            arg = argv[idx]
            if arg in node.children:
                node = node.children[arg]
                path.append(arg)
                idx += 1
            else:
                break
        return node, path, argv[idx:]

    def collect_recursive(self, prefix=()):
        out = []
        if self.func is not None:
            out.append((prefix, self))
        for c in self.children.values():
            out.extend(c.collect_recursive(prefix + (c.name,)))
        return out

    def collect_structure(self, prefix=()):
        out = []
        children_keys = list(self.children.keys())
        out.append((prefix, self, children_keys))
        for c in self.children.values():
            out.extend(c.collect_structure(prefix + (c.name,)))
        return out

class CLIGroup:
    def __init__(self, name='group', desc=""):
        self.root = CommandNode(name, desc)
        self.name = name
        self.desc = desc

    def cmd(self, path, help=None, completion=None):
        parts = path.strip('/').split('/')
        def decorator(func):
            node = self.root
            for part in parts:
                node = node.get_or_create_child(part)
            node.func = func
            node.help = help or ""
            node.completion = completion or {}
            node.signature = inspect.signature(func)
            return func
        return decorator

    def include_group(self, group, prefix=""):
        prefix_parts = [p for p in prefix.strip('/').split('/') if p]
        node = self.root
        for part in prefix_parts:
            node = node.get_or_create_child(part)
        def copy_subtree(from_node, to_node):
            if from_node.func is not None:
                to_node.func = from_node.func
                to_node.help = from_node.help
                to_node.completion = from_node.completion
                to_node.signature = from_node.signature
            for cname, child in from_node.children.items():
                copy_subtree(child, to_node.get_or_create_child(cname))
        copy_subtree(group.root, node)

class CLI:
    def __init__(self, name='cli', desc=""):
        self.root = CommandNode(name, desc)
        self.name = name
        self.desc = desc

    def cmd(self, path, help=None, completion=None):
        parts = path.strip('/').split('/')
        def decorator(func):
            node = self.root
            for part in parts:
                node = node.get_or_create_child(part)
            node.func = func
            node.help = help or ""
            node.completion = completion or {}
            node.signature = inspect.signature(func)
            return func
        return decorator

    def include_group(self, group, prefix=""):
        prefix_parts = [p for p in prefix.strip('/').split('/') if p]
        node = self.root
        for part in prefix_parts:
            node = node.get_or_create_child(part)
        def copy_subtree(from_node, to_node):
            if from_node.func is not None:
                to_node.func = from_node.func
                to_node.help = from_node.help
                to_node.completion = from_node.completion
                to_node.signature = from_node.signature
            for cname, child in from_node.children.items():
                copy_subtree(child, to_node.get_or_create_child(cname))
        copy_subtree(group.root, node)

    def find_node(self, argv):
        return self.root.find_node(argv)

    def exec(self, args=None):
        argv = sys.argv[1:] if args is None else args
        if '--completion' in argv:
            self.print_completion()
            sys.exit(0)
        if not argv:
            self.show_help()
            sys.exit(1)
        node, path, remaining = self.find_node(argv)
        if node.func is None:
            if node.children:
                print(f"Usage: {self.name} {' '.join(path)} <subcommand> [options]")
                print("Subcommands:", ' '.join(node.children.keys()))
                sys.exit(1)
            else:
                print(f"Unknown command: {' '.join(argv)}")
                self.show_help()
                sys.exit(1)
        params = list(node.signature.parameters.values())
        ap = argparse.ArgumentParser(prog=f"{self.name} {' '.join(path)}", add_help=True)
        for p in params:
            ap.add_argument(f"--{p.name}", dest="op_" + p.name, required=False)
            ap.add_argument(p.name, nargs='?', default=None)
        ns, _ = ap.parse_known_args(remaining)
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
        node.func(**kw)

    def show_help(self):
        print(f"usage: {self.name} <command> [<args>]\n")
        for prefix, node, children in self.root.collect_structure():
            if prefix:
                cmdpath = ' '.join(prefix)
                desc = node.help if node.help else ""
                if node.func is not None:
                    print(f"  {cmdpath} - {desc}")
                if children:
                    print(f"  {cmdpath}: subcommands: {', '.join(children)}")
            else:
                if children:
                    print("Available commands:", ', '.join(children))

    def print_completion(self):
        nodes = {}
        for prefix, node in self.root.collect_recursive():
            label = "_".join(prefix)
            nodes[label] = (prefix, node)
        all_cmds = set()
        subcmds_map = {}
        opt_map = {}
        val_map = {}
        for prefix, node, children in self.root.collect_structure():
            if len(prefix) == 0:
                all_cmds.update(children)
            else:
                pfx = "_".join(prefix)
                if children:
                    subcmds_map[pfx] = children
        for label, (prefix, node) in nodes.items():
            opt_map.setdefault(label, [])
            if node.signature is not None:
                for p in node.signature.parameters.values():
                    opt = f"--{p.name}"
                    if opt not in opt_map[label]:
                        opt_map[label].append(opt)
            if node.completion:
                val_map.setdefault(label, {})
                for arg, vals in node.completion.items():
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
            f'_{self.name}_completion() {{',
            '    local cur prev words cword',
            '    COMPREPLY=()',
            '    cur="${COMP_WORDS[COMP_CWORD]}"',
            '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
            '    words=("${COMP_WORDS[@]}")',
            '    cword=$COMP_CWORD',
            '',
            f'    cmds="{ " ".join(sorted(all_cmds)) }"',
            '',
            '    declare -A subcmds',
        ]
        for k, subs in subcmds_map.items():
            script.append(f'    subcmds["{k}"]="{ " ".join(subs) }"')
        script.append('    declare -A opts')
        for label, optlist in opt_map.items():
            script.append(f'    opts["{label}"]="{ " ".join(optlist) }"')
        script.extend([
            '    path=()',
            '    label=""',
            '    search_subcmds() {',
            '      local i=1',
            '      local curr=""; label=""; path=()',
            '      while (( i<=cword )); do',
            '        curr="${words[i]}"',
            '        [[ "$curr" == --* ]] && break',
            '        if [[ "$label" == "" ]]; then',
            '          label="$curr"',
            '        else',
            '          label="${label}_$curr"',
            '        fi',
            '        if [[ -n "${subcmds[$label]}" ]]; then',
            '          path+=("$curr")',
            '          ((i++))',
            '        else',
            '          break',
            '        fi',
            '      done',
            '    }',
            '',
            '    if [[ $cword -eq 1 ]]; then',
            '        COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )',
            '        return 0',
            '    fi',
            '',
            '    search_subcmds',
            '    sub_label="$label"',
            '    pfxlen=${#path[@]}',
            '',
            '    if [[ $pfxlen -gt 0 ]]; then',
            '        subkey="$sub_label"',
            '        if [[ $cword -eq $((pfxlen+1)) ]]; then',
            '            if [[ -n "${subcmds[$subkey]}" ]]; then',
            '                COMPREPLY=( $(compgen -W "${subcmds[$subkey]}" -- "$cur") )',
            '            fi',
            '            if [[ -n "${opts[$subkey]}" ]]; then',
            '                COMPREPLY+=( $(compgen -W "${opts[$subkey]}" -- "$cur") )',
            '            fi',
            '            return 0',
            '        fi',
            '        if [[ -n "${opts[$subkey]}" ]]; then',
            '            COMPREPLY+=( $(compgen -W "${opts[$subkey]}" -- "$cur") )',
            '        fi',
            '    fi',
            '',
            '    if [[ "$prev" == --* ]]; then',
            '        argname="${prev#--}"',
            '        arrvar="_COMP_${sub_label//[^a-zA-Z0-9_]/_}__${argname}"',
            '        if declare -p $arrvar &>/dev/null; then',
            r'            COMPREPLY=( $(compgen -W "$(eval "echo \${${arrvar}[@]}")" -- "$cur") )',
            '            return 0',
            '        fi',
            '    elif [[ "$cur" == --*=* ]]; then',
            '        argname="${cur%%=*}"',
            '        argname="${argname#--}"',
            '        arrvar="_COMP_${sub_label//[^a-zA-Z0-9_]/_}__${argname}"',
            '        if declare -p $arrvar &>/dev/null; then',
            r'            COMPREPLY=( $(compgen -W "$(eval "echo \${${arrvar}[@]}")" -- "") )',
            '            return 0',
            '        fi',
            '    fi',
            '    return 0',
            '}',
            f'complete -F _{self.name}_completion {self.name}'
        ])
        print('\n'.join(script))
