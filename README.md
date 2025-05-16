# About

`cly` is a lightweight solution to build Python CLIs quickly following a [fastAPI](https://github.com/fastapi/fastapi)-like syntax. No dependencies.

# Install

With `pip`:

```
pip install git+https://github.com/pythonalta/cly
```

With [py](https://github.com/ximenesyuri/py):

```
py install pythonalta/cly --from github 
```

# Usage

In `cly` you create a CLI as you create an app in `fastAPI`:

```python
## in cli.py 
from cly import CLI
cli = CLI(name="my_cli", desc="Some description")
```

And you execute the CLI as you execute the app in `fastAPI`:

```python
## in cli.py
if __name__ = '__main___':
    cli.exec()
```

Also, you add commands as you add routers:

```python
## in cli.py
@cli.cmd('/my_command', help='This is a help message')
def my_command_callback(arg1, arg2, ...):
    ...
```
   
The above will produce the command `my_command` which has the arguments `arg1`, `arg2`, etc. The arguments, themselves can be called as positional arguments or keyword arguments. In other words, all the following options will work:

```bash
# positional arguments 
python cli.py my_command arg1_value arg2_value ...
# keyword arguments
python cli.py my_command --arg1=arg1_value --arg2=arg2_value ...
# alternative keyword argument
python cli.py my_command --arg1 arg1_value --arg2 arg2_value ...       
```

Subcommands are created as you create subendpoints:
 
```python
## in cli.py
@cli.cmd('/my_command/subcommand', help='This is another help message')
def subcommand_callback(argA, argB, ...):
    ...
```

The above will provide:

```bash
python cli.py my_command subcommand argA_value argB_value ...
```

Furthermore, you can organize commands in groups as, in `fastAPI`, you organize endpoints in routers:

```python
# in groups/group1.py
from cly import CLIGroup

cli_group1 = CLIGroup(name='cli_group1', desc='First group of commands')

@cli_group1.cmd('/command', help="some help message")
def group_command_callback(arg1, arg2, ...):
    ...

# in cli.py
from cly import CLI
from groups.group1 import cli_group1

cli = CLI(name="my_cli", desc="Some description")
cli.include_group(cli_group1, preffix='group1')
```

# Completion

When you create a CLI with the `CLI` class from `cly`, it comes equipped with a `--completion` option, which prints a `Bash` completion script for your CLI.

```bash
# print the completion script
python cli.py --completion
```
To use it, you should save the script in a file and source the file in your `.bashrc`.

```bash
# save the completion script
python cli.py --completion > /path/to/completion.sh
# use it 
echo "source /path/to/completion.sh" >> $HOME/.bashrc
```

The completion script suggests for commands, subcommands and arguments. You can quickly define suggestions for argument values of some command by using the `completion` directive when defining the command decorator:

```python
@cli.cmd(
    '/my_command',
    help='This is another help message',
    completion={
        'arg1' = ['value1', 'value2', ...],
        ...
    }
)
def my_command_callback(arg1, arg2, ...):
    ...
```

The, when you hit 

```bash
python cli.py my_command arg1 <tab>
```
      
it will suggest for `value1`, `value2`, etc, in the same ordering you provided in the `completion` directive.

# To Do

1. add type checking for the argument values
2. allow the use of variables in the definition of commands, as you can do for endpoints in `fastAPI`.
3. include an option to turn the CLI globally available
