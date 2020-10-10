import os
import sys
import subprocess
import platform
import re
import datetime
import time
import pathlib # TODO look at if this is easier for the os.path code - ideally lets keep it all consistent (ie one or other way); think perhaps this'll be easier for handling Windows compatibility
import json

import click
import questionary
from prompt_toolkit.styles import Style
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.padding import Padding
from rich.markdown import Markdown
from rich.theme import Theme
from rich.text import Text
import confuse


try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as pkg_resources

# for use with local resources
from . import example_files
from . import instructions
from . import data as data_dir

APPNAME = 'gatherup'
QUIT = False
LANGUAGES = {
    'en':'English',
    'de':'Deutsch',
    'fr':'Francais',
    'hi':'हिन्दी'          # Hindi
    }
#TODO: get these translations done (once the basic English version has been firmed up)
#    'es':'Español'
#    'zh':'Zhōngwén',     # Chinese
#    }

USER_REPLACED_LINE = '[Replace this text with comments]'

PROJECT = ''
SOURCE_HOST = ''
BEFORE_YOU_START_LINK = ''
SOURCE_HOST_NEW_ISSUE_LINK = ''
DISCOURSE_TOPIC_LINK = ''


@click.version_option(version='0.0.4-alpha')
@click.option('-s', '--setup', is_flag=True, help='Setup user config file and offer to install example files in app directory')
@click.option('-m', '--demo', is_flag=True, help='Demo of formatted output using built-in example files')
@click.option('-p', '--project', type=str, help='Select project name (uses details, where found, in "project_details.txt").')
@click.option('-l', '--lang', type=click.Choice(list(LANGUAGES.keys()), case_sensitive=False), help='Select language for instructions (ISO_639-1).')
@click.option('-n', '--no_instruct', is_flag=True, help='Suppress question for / display of instructions.')
@click.option('-d', '--debug', is_flag=True, help='Show debug information during usage.')
@click.command()
def gatherup(project, no_instruct, lang, debug, setup, demo):
    """GatherUp helps you post essential Python config details to GitHub
       or Discourse, all beautifully formatted"""

    global config, console, qs, rich_theme, questionary_style, autocomplete_style

    config_file = get_config_file()

    if config_file != '':
        config = set_config()
    else:
        config = None

    rich_theme = Theme({
        "h1": "bold grey0 on yellow1",
        "h2": "bold hot_pink",
        "ul": "bold white",
        "t1": "bold yellow1",
        "t2": "bold spring_green3",
        "bw": "bold white",
        "edge": "grey23",
        "link": "dodger_blue3",
        "markers":"white italic bold on deep_pink1"
    })

    questionary_style = Style([
        ('qmark', 'fg:#00d75f bold'),       # token in front of the question
        ('expected', 'bold'),                # the expected value we think the user has
        ('question', 'bold'),               # question text
        ('answer', 'fg:#ffff00 bold'),      # submitted answer text behind the question
        ('pointer', 'fg:#ff5fd7 bold'),     # pointer used in select and checkbox prompts
        ('highlighted', 'fg:#ff5fd7 bold'), # pointed-at choice in select and checkbox prompts
        ('selected', 'fg:#949494'),         # style for a selected item of a checkbox
        ('instruction', ''),                # user instructions for select, rawselect, checkbox
        ('text', ''),                       # plain text
        ('disabled', 'fg:#858585 italic')   # disabled choices for select and checkbox prompts
    ])

    autocomplete_style = Style([
        ('qmark', 'fg:#00d75f bold'),       # token in front of the question - CORRECT
        #('expected', 'fg:#000000 bg:#ffffff bold'),                # the expected value we think the user has NOT USED
        ('question', 'bold'),               # question text - CORRECT, IS FOR QUESTION TEXT
        ('answer', 'fg:#00d75f bg:#322e2e bold'),      # submitted answer text behind the question - ACTUALLY USED FOR PRIMARY DROP-DOWN
        #('pointer', 'fg:#ffffff bg:#000000 bold'),     # pointer used in select and checkbox prompts NOT USED
        #('highlighted', 'fg:#ffffff bg:#000000 bold'), # pointed-at choice in select and checkbox prompts NOT USED
        #('selected', 'fg:#000000 bg:#ffffff'),         # style for a selected item of a checkbox SELECTED PRIMARY DROP-DOWN, OTHERWISE SEEMS TO INVERT???
        ('text', 'fg:#322e2e')                       # plain text - ACTUALLY USED FOR SECONDARY DROP-DOWN
    ])


    console = Console(width=120, theme=rich_theme)
    qs = questionary

    if debug:
        console.print('\nDEBUG IS ON')
        console.print(f'Options:\n\t --lang {lang}')
        console.print(f'\t --no_instruct {no_instruct}')
        console.print(f'\t --project {project}')
        if config is None:
            console.print('There is no config file')
        else:
            console.print(f'Config file: {config_file}')

    gather_intro(debug=debug)

    #TODO: remove this once languages work beyond instructions only
    if not no_instruct:
        lang = get_language_choice(LANGUAGES, lang, debug=debug)
    else:
        lang = 'en'

    if setup:
        do_setup()

    if demo:
        do_demo()
        #TODO proper quit
        return

    while not QUIT: 
        if not no_instruct:
            offer_instructions(lang, debug=debug)
        output_text = gather_input(project, debug=debug)
        handle_output(output_text, debug=debug)
        check_successful(debug=debug)
    finished(debug=debug)


def do_setup():
    """Creates a gatherup config file and offers to install example_files"""
    global config
    console.print('\n[bw]     Starting setup...[/bw]')
    console.print('[bw]     Trying to setup files in standard config location[/bw]')
    config_path = 'NOT SET'
    try:
        config = set_config()
        config_path = config.user_config_path()
    except Exception as e:
        raise e
    # Read the standard config from the imported package data_dir and save it to the config file
    config_contents = pkg_resources.read_text(data_dir, confuse.CONFIG_FILENAME)
    # TODO Check for file existance and warn about overwriting
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_contents)
    console.print(f'[bw]     GatherUp configuration file is: [t2]{config_path}[/t2][/bw]')
    config = set_config() # TODO get this working better (silly it's called twice here...)

    if config['project_details']:
        project_path = config['project_details'].as_path()
        project_details_text = pkg_resources.read_text(data_dir, project_path.name)
        try:
            # TODO Check for file existance and warn about overwriting
            project_path.parent.mkdir(parents=True, exist_ok=True)
            with open(project_path, 'w', encoding='utf-8') as fh:
                fh.write(project_details_text)
            console.print(f'[bw]     project_details.txt file is: [t2]{project_path}[/t2][/bw]')
        except Exception as e:
            raise e

    examples = ['example_config_1','log_with_traceback','log_without_traceback']
    for example in examples:
        if config[example]:
            example_path = config[example].as_path()
            example_text = pkg_resources.read_text(example_files, example_path.name)
            try:
                # TODO Check for file existance and warn about overwriting
                example_path.parent.mkdir(parents=True, exist_ok=True)
                with open(example_path, 'w', encoding='utf-8') as fh:
                    fh.write(example_text)
                console.print(f'[bw]     Example file saved: [t2]{example_path}[/t2][/bw]')
            except Exception as e:
                raise e
    console.print('[bw]     Setup completed[/bw]\n\n')


def do_demo():
    """Demo of formatted output using built-in example files"""
    demo_text = '# Blistering Barnacles!!\n\n:rainbow: Look! :unicorn: Is that _really_ it?\n\n**Yes** it is!\n\nIt\'s DEMO MODE\n\nSome wonderful **formatted text** to paste.\n\n_If this were real (and not the demo) there would be useful Python related information here_\n\n:bee: Best you don\'t actually submit this :slightly_smiling_face:'
    screen_output(output_text = demo_text)


def get_project_details(project_path='', debug=None):
    #project_path='data/project_details.txt'
    project_dict = {}
    if config is not None:
        if config['project_details']:
            project_path = config['project_details'].as_filename()
            if debug:
                console.print(f'\nDEBUG: {project_path}')


            with open(project_path, encoding='utf-8') as fh:
                project_details_text = fh.read()
        else:
            project_details_text = ''
    else:
        project_details_text = pkg_resources.read_text(data_dir, 'project_details.txt')

    for line in project_details_text.splitlines():
        fields = line.split('|')
        if fields[0].strip() == 'Project Name' or fields[0][0] == '#':
            continue
        else:
            output_details = []
            raw_details = fields[1:]
            for k, v in enumerate(raw_details):
                if k < 2:
                    output_details.append(v.lower() == 'true')
                else:
                    output_details.append(v.strip())
            project_dict[fields[0].strip()] = output_details
    if debug:
        console.print(f'\nDEBUG: Project details dictionary:', project_dict, '\n\n', end='')
    return project_dict

def reverse_readline(filename, buf_size=8192):
    """A generator that returns the lines of a file in reverse order"""
    with open(filename, encoding='utf-8') as fh:
        segment = None
        offset = 0
        fh.seek(0, os.SEEK_END)
        file_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(file_size, offset + buf_size)
            fh.seek(file_size - offset)
            buffer = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buffer.split('\n')
            # The first line of the buffer is probably not a complete line so
            # we'll save it and append it to the last line of the next buffer
            # we read
            if segment is not None:
                # If the previous chunk starts right from the beginning of line
                # do not concat the segment to the last line of new chunk.
                # Instead, yield the segment first 
                if buffer[-1] != '\n':
                    lines[-1] += segment
                else:
                    yield segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if lines[index]:
                    yield lines[index]
        # Don't yield None if the file was empty
        if segment is not None:
            yield segment

def get_conda_environments_metadata(debug=None):
    """Returns dict of conda environment name and corresponding path"""

    env_metadata = {}

    cmd_list = ['conda', 'env', 'list', '--json']
    try:
            run_cmd = subprocess.Popen(cmd_list, stdout=subprocess.PIPE)
    except Exception as e:
        if debug:
            cmd_text = ' '.join(cmd_list)
            console.print(f'Error calling Conda ({cmd_text})\n', e)
            return env_metadata

    try:
        json_input = run_cmd.communicate()[0].decode('utf-8')
    except Exception as e:
        console.print(f'Error reading environment details with Conda\n', e)
        return env_metadata

    try:
        data = json.loads(json_input)
        for item in data['envs']:
            env_metadata[pathlib.PurePath(item).name] = item
    except Exception as e:
        console.print(f'Error processing Conda environment list\n',e)

    return env_metadata


def get_packages(condaenv_name=None, virtualenv_activate=None, debug=None):
    """Returns GH markdown text for formatted table of packages. Assumes conda
    is being used if present in sys.executable otherwise falls back to pip """

    package_count = 0
    package_table = ''
    python_version = 'Unknown'

    # conda None + venv None --> decide based on sys.executable
    #   if contains conda --> conda, else --> pip

    # conda SET + venv None --> conda
    # conda None + venv SET --> pip
    # conda SET + venv SET -->   a mistake, just do arbitrary first one (ie conda)

    if condaenv_name is None and virtualenv_activate is None:
        is_conda = 'conda' in sys.executable.lower()
    else:
        is_conda = False # may well have conda installed but need to heed the inputs

    if is_conda or condaenv_name is not None:
        installer = 'Conda'
        # Command: conda list --json
        if condaenv_name is None:
            installer_cmd_list = ['conda', 'list', '--json']
        else:
            installer_cmd_list = ['conda', 'list', '-n', f'{condaenv_name}', '--json']
    else:
        installer = 'Pip'
        #source venv/bin/activate

        # Command: pip list --format json
        if virtualenv_activate is None:
            installer_cmd_list = ['pip', 'list', '--format', 'json']
        else:
            #TODO add is_file check on virtualenv_activate
            installer_cmd_list = ['bash', '-c', f'source {virtualenv_activate} && pip list --format json']

    try:
        run_cmd = subprocess.Popen(installer_cmd_list, stdout=subprocess.PIPE)
    except Exception as e:
        console.print(f'Error calling installer ({installer})\n', e)
        return package_table, package_count, python_version

    try:
        json_input = run_cmd.communicate()[0].decode('utf-8')
    except Exception as e:
        console.print(f'Error reading package details ({installer})\n', e)
        return package_table, package_count, python_version

    ## Example format for Pip:
    #json_input = '[{"name": "certifi", "version": "2020.6.20"}, {"name": "colorama", "version": "0.4.3"}]'

    ## Example format for Conda:
    # json_input = """[
    #   {
    #     "base_url": "https://conda.anaconda.org/conda-forge",
    #     "build_number": 0,
    #     "build_string": "conda_forge",
    #     "channel": "conda-forge",
    #     "dist_name": "_libgcc_mutex-0.1-conda_forge",
    #     "name": "_libgcc_mutex",
    #     "platform": "linux-64",
    #     "version": "0.1"
    #   },
    #   {
    #     "base_url": "https://conda.anaconda.org/conda-forge",
    #     "build_number": 4,
    #     "build_string": "0_gnu",
    #     "channel": "conda-forge",
    #     "dist_name": "_openmp_mutex-4.5-0_gnu",
    #     "name": "_openmp_mutex",
    #     "platform": "linux-64",
    #     "version": "4.5"
    #   }
    # ]"""

    try:
        data = json.loads(json_input)
        #package_table = '| Package  | Version |\n| ------------- | ------------- |\n| Content Cell  | Content Cell  |\n| Content Cell  | Content Cell  |\n\n'
        package_table = f':package: Package list from {installer}\n\n| Package  | Version |\n| ------------- | ------------- |\n'
        for item in data:
            package_table = package_table + '|' + item['name'] + '|' + item['version'] + '|\n'
            if item['name'].lower() == 'python':
                python_version = item['version']
        package_table = package_table + '\n'
        package_count = len(data)
    except Exception as e:
        console.print(f'Error processing installed packages ({installer})\n',e)

    try:
        if virtualenv_activate is not None:
            python_cmd_list = ['bash', '-c', f'source {virtualenv_activate} && python --version']
            run_cmd = subprocess.Popen(python_cmd_list, stdout=subprocess.PIPE)
            python_version_output = run_cmd.communicate()[0].decode('utf-8')
            python_version = python_version_output.split(' ')[1]
    except Exception as e:
        raise console.print('Error establishing Python version in virtual environment\n',e)

    return package_table, package_count, python_version

def get_traceback_from_log(log_file_path, debug=None):

    rx = re.compile(r'''
        ^Traceback
        [\s\S]+?
        (?=^\[|\Z)
        ''', re.M | re.X)

    traceback_contents = ''
    end_contents = ''
    done = False

    for line in reverse_readline(log_file_path):
        if done: break
        #print(line)
        end_contents = line + '\n' + end_contents
        for match in rx.finditer(end_contents):
            traceback_contents = end_contents
            done = True
            break
    return traceback_contents

def get_file_path(default_path=None, file_description=None, debug=None):
    if default_path is None:
        default_path = 'example_files/example_config.json'
    if file_description is None:
        file_description = 'file'

    questions = [{
        'type': 'text',
        'name': 'question_file',
        'message': f'What is the path and name for the {file_description}?',
        'default': f'{default_path}',
        'validate': lambda val: val == '' or os.path.isfile(val)
    }]
    results = qs.prompt(questions, style=questionary_style, qmark='   ?')
    return results['question_file']


def get_project_selection(project_name=None, debug=None):

    project_dict = get_project_details()

    project_list = [p for p in project_dict]

    if project_name is None:
        project_list.append('Generic Project')
        questions = [{
            'type': 'autocomplete',
            'name': 'question_project',
            'message': 'Which project are you using?\n     (press <Tab> for list, up and down to select and/or type to narrow selection)',
            'choices': project_list,
            'ignore_case': True,
            'validate': lambda val: val in project_list
        }]
        results = qs.prompt(questions, style=autocomplete_style, qmark='   ?')
    else:
        results = {}
        results['question_project'] = project_name
    
    if results['question_project'] in project_dict:
        # TODO make this more generic so we return all the fields
        project = results['question_project']
        source_host = project_dict[results['question_project']][2] # remember, there is one fewer items in the list due to project name being the key in the dict
        source_host_new_issue_link = project_dict[results['question_project']][3]
        discource_topic_link = project_dict[results['question_project']][5]
        before_you_start_link = project_dict[results['question_project']][7]
    else:
        if project_name is not None:
            project = project_name
        else:
            project = 'Project'
        source_host = 'Source'
        source_host_new_issue_link = ''
        discource_topic_link = ''
        before_you_start_link = ''

    return project, source_host, source_host_new_issue_link, discource_topic_link, before_you_start_link

def get_conda_env(debug=None):

    env_metadata = get_conda_environments_metadata()
    if debug:
        console.print(f'\nDEBUG: Conda environment metadata: {env_metadata}')

    questions = [{
        'type': 'autocomplete',
        'name': 'question_conda_env',
        'message': 'Which Conda environment are you using?\n     (press <Tab> for list and/or type to narrow selection)',
        'choices': [e for e in env_metadata],
        'meta_information': env_metadata,
        'ignore_case': True,
        'validate': lambda val: val == '' or val in env_metadata
    }]
    results = qs.prompt(questions, style=autocomplete_style, qmark='   ?')
    return results['question_conda_env']


def get_entire_file(file_path, debug=None):
    contents = ''
    with open(file_path, encoding='utf-8') as afile:
        for line in afile:
            contents = contents + line
    return contents


def gather_intro(debug=None):
    #os.system('cls' if os.name == 'nt' else 'clear') # whilst it is neater, if the user loses important/helpful output on screen this will be frustrating
    console.print('\n')
    text = Text.assemble(('  GatherUp  ', 'h1'), ('\nStreamline posting key details to GitHub and Discourse', 'bw'))
    console.print(Panel(Padding(text, (1,4)), box=box.ROUNDED, style="edge"))


def screen_output(output_text, marker_start='\n>>> COPY-TEXT-BELOW-DOWN-TO-STOP-MARKER  \n', marker_stop='>>> STOP-HERE-EXCLUDING-THIS-LINE  \n', debug=None):
    console.print('\n[bw]     In a moment your answers will appear below, formatted ready to post online[/bw]\n')
    console.print(marker_start, style='markers')
    time.sleep(2)
    print(output_text)
    console.print(marker_stop, style='markers')
    console.print('\n[bw]     Now you can proceed to post the copied text on GitHub or Discourse[/bw]')
    if SOURCE_HOST_NEW_ISSUE_LINK != '':
        console.print(f'\n      - [link]{SOURCE_HOST_NEW_ISSUE_LINK}[/link]\n      - [link]{DISCOURSE_TOPIC_LINK}[/link]')
    time.sleep(1)


def handle_output(output_text, debug=None):
    screen_output(output_text = output_text)


def indent_text(input_text, indent_count=4, debug=None):
    output_text = ''
    indent = ' ' * indent_count
    for line in input_text.splitlines(True):
        output_text = output_text + indent + line
    return output_text


def run_once(f):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper

@run_once
def notify_setup():
    """Notifies user of setup option in relation to example paths"""
    if config is None:  # confirm that this has not triggered due to user setting config to exclude examples (or the reminder would be annoying!)
        console.print('\n[bw]     As there is no config, example files are not available.\n     Run with [t2]--setup[/t2] option to add them and the path below will be pre-populated with a relevant example[/bw]\n\n')


def gather_input(project_name=None, debug=None):
    
    global PROJECT
    global SOURCE_HOST
    global BEFORE_YOU_START_LINK
    global SOURCE_HOST_NEW_ISSUE_LINK
    global DISCOURSE_TOPIC_LINK

    # Prepare OS choices and put our best guess at current OS first (ie to streamline response)
    os_default = str(platform.system())
    os_choices = [
            'Linux',
            'Mac',
            'Windows',
            'Other',
            qs.Separator(),
            'Skip']
    if os_default in os_choices:
        os_choices.insert(0, os_choices.pop(os_choices.index(os_default)))

    PROJECT, SOURCE_HOST, SOURCE_HOST_NEW_ISSUE_LINK, DISCOURSE_TOPIC_LINK, BEFORE_YOU_START_LINK = get_project_selection(project_name)

    # Generate our question structure in two batches
    question_batch_1 = [{
        'type': 'select',
        'name': 'question_os',
        'message': 'What OS are you using?',
        'choices': os_choices,
    },
    {
        'type': 'text',
        'name': 'question_os',
        'message': 'Insert OS name as free text',
        'when': lambda x: x['question_os'] == 'Other'
    },
    {
        'type': 'select',
        'name': 'question_read_package_list',
        'message': 'Do you wish to import an environment package list?',
        'choices': [
            'Yes, from the current environment',
            'Yes, from a designated virtual environment',
            'Yes, from a designated Conda environment',
            qs.Separator(),
            'No, skip this'
        ],
    },
    {
        'type': 'select',
        'name': 'question_env',
        'message': 'What kind of environment / virtual environment are you using?',
        'when': lambda x: x['question_read_package_list'] in ('Yes, from the current environment', 'No, skip this'),
        'choices': [
            'Venv / virtualenv',
            'Conda',
            'Not using a virtual environment',
            'Other',
            qs.Separator(),
            'Skip'
        ],
    },
    {
        'type': 'text',
        'name': 'question_env',
        'message': 'Insert environment / virtual environment as free text',
        'when': lambda x: 'question_env' in x and x['question_env'] == 'Other'
    }]

    results_1 = qs.prompt(question_batch_1, style=questionary_style, qmark='   ?')
    if debug:
        console.print('\nDEBUG: Question Responses 1: ', results_1, '\n\n', end='') # small workaround here for the list issue in Rich (https://github.com/willmcgugan/rich/issues/162)
    results = results_1

    python_version = 'Unknown'

    condaenv_name = None
    virtualenv_activate = None
    if results['question_read_package_list'] == 'Yes, from a designated Conda environment':
        #condaenv_name = 'youtube-dl'
        condaenv_name = get_conda_env()
        # Can assume this without asking the user
        results['question_env'] = 'Conda'

    if results['question_read_package_list'] == 'Yes, from a designated virtual environment':
        #virtualenv_activate = 'venv/bin/activate'
        virtualenv_activate = get_file_path('venv/bin/activate', 'virtualenv activation file')
        # Can assume this without asking the user
        results['question_env'] = 'Venv / virtualenv'

    if results['question_read_package_list'] != 'No, skip this':
        # Need to do this prior to getting the platform python version, which must come before we ask batch 2 questions
        package_table, package_count, python_version = get_packages(condaenv_name, virtualenv_activate)

    if python_version == 'Unknown':
        python_version = str(platform.python_version())
        if debug:
            console.print(f'\nDEBUG: Obtained current Python version via local platform.python_version: {python_version}')

    python_version = python_version.strip()

    question_batch_2 = [{
        'type': 'select',
        'name': 'question_version',
        'message': 'What version of Python are you using?',
        'choices': [
            python_version,
            'Other',
            qs.Separator(),
            'Skip'
        ],
    },
    {
        'type': 'text',
        'name': 'question_version',
        'message': 'Insert version number (preferably major.minor.patchlevel) as free text',
        'when': lambda x: x['question_version'] == 'Other'
    },
    {
        'type': 'select',
        'name': 'question_install',
        'message': f'How was {PROJECT} installed?',
        'choices': [
            #TODO: dynamically adjust this list to reflect the project source settings (but leave all for a "Generic" project)
            'Pip install',
            'Conda install',
            f'From source on {SOURCE_HOST}',
            'Other',
            qs.Separator(),
            'Skip'
        ],
    },
    {
        'type': 'checkbox',
        'name': 'question_provide',
        'message': 'What do you want to provide?',
        'choices': [
            'Submit config.json',
            'Submit traceback from logs',
            'Submit entire log',
            #qs.Separator(),
            #'Skip'
        ]
        #TODO: add validation if questionary https://github.com/tmbo/questionary/pull/48 is accepted; stop users overshooting this by accident
    }
    ]

    results_2 = qs.prompt(question_batch_2, style=questionary_style, qmark='   ?')
    if debug:
        console.print('\nDEBUG: Question Responses 2: ', results_2, '\n\n', end='') # small workaround here for the list issue in Rich (https://github.com/willmcgugan/rich/issues/162)
    results.update(results_2)

    # Gradually build up our output text string:
    output_text = f'\n{USER_REPLACED_LINE}\n\n## Details\n\n'

    if results['question_os'].strip() not in ('Skip',''):
        output_text = output_text + f'### Platform OS\n\n* **{results["question_os"]}**\n\n'

    if not (results['question_version'].strip() in ('Skip', '') and results['question_env'].strip() in ('Skip', '')):
        output_text = output_text + f'### Python Environment\n\n'
        if results['question_version'].strip() not in ('Skip', ''):
            output_text = output_text + f'* **Python {results["question_version"].strip()}**\n\n'
        if results['question_env'].strip() not in ('Skip', ''):
            output_text = output_text + f'* Virtual env: **{results["question_env"].strip()}**\n\n'

    if not(results['question_install'].strip() not in ('Skip', '') and not(results['question_read_package_list'])):
        output_text = output_text + f'### Package Installation\n\n'
        if results['question_install'].strip() not in ('Skip', ''):
            install_choices = {'Pip install':'via Pip', 'Conda install': 'via Conda', f'From source on {SOURCE_HOST}':f'from source on {SOURCE_HOST}'}
            if results['question_install'] in install_choices:
                install_action = install_choices[results['question_install']]
            else:
                install_action = results['question_install'].strip()
            output_text = output_text + f'* {PROJECT} installed {install_action}\n<br>\n' # <br> is present to slightly improve layout in Discourse (although then looks slightly worse in GitHub!)

        if results['question_read_package_list'] != 'No, skip this':
            # previously updated package_count, package_table
            if package_count > 0:
                output_text = output_text + wrap_collapse(package_table, f'Click to see package list (package count: {package_count})')

    if 'Submit config.json' in results['question_provide']:
        prefilled_path = ''
        if config is not None:
            if config['example_config_1']:
                prefilled_path = config['example_config_1'].as_filename()
        if prefilled_path == '':
            notify_setup()
        config_file_path = get_file_path(prefilled_path, 'config file')
        if config_file_path != '':
            details = get_entire_file(config_file_path)
            line_count = details.count('\n') + 1
            filetype_formatting = {'.json':'javascript', '.ini':'ini', '.toml':'', '.yaml':'yaml'}
            config_extn = pathlib.Path(config_file_path).suffix.lower()
            if config_extn in filetype_formatting:
                config_format_code = filetype_formatting[config_extn]
            else:
                config_format_code = ''
            formatted_details = wrap_text(details, f'````{config_format_code}', '````') # Can use json but this formats comments awkwardly
            output_text = output_text + '## Configuration\n\n'
            output_text = output_text + wrap_collapse(f':page_facing_up: Contents from: **{config_file_path}**\n\n{formatted_details}\n\n', f'Click to see config file (lines: {line_count})')

    if 'Submit traceback from logs' in results['question_provide']:
        prefilled_path = ''
        if config is not None:
            if config['log_with_traceback']:
                prefilled_path = config['log_with_traceback'].as_filename()
        if prefilled_path == '':
            notify_setup()
        log_file_path = get_file_path(prefilled_path, 'log file with the traceback')
        if log_file_path != '':
            details = get_traceback_from_log(log_file_path)
            traceback_len = len(details.strip())
            if debug:
                print(f'Traceback length: {traceback_len}')
            if traceback_len > 0:
                line_count = details.strip().count('\n') + 1
                formatted_details = wrap_text(details, '~~~')
                output_text = output_text + '## Traceback\n\n'
                output_text = output_text + wrap_collapse(f':page_facing_up: Traceback extract from: **{log_file_path}**\n\n{formatted_details}\n\n', f'Click to see traceback extract (lines: {line_count})')

    if 'Submit entire log' in results['question_provide']:
        prefilled_path = ''
        if config is not None:
            if config['log_with_traceback']:
                prefilled_path = config['log_with_traceback'].as_filename()
        if prefilled_path == '':
            notify_setup()
        log_file_path = get_file_path(prefilled_path, 'log file for submission')
        if log_file_path != '':
            details = get_entire_file(log_file_path)
            line_count = details.count('\n') + 1
            output_text = output_text + '## Logfile\n\n'
            output_text = output_text + wrap_collapse(f':page_facing_up: Logfile: **{log_file_path}**\n\n{indent_text(details)}\n\n', f'Click to see log file (lines: {line_count})')

    output_text = output_text + create_generated_by_message()
    return output_text

def wrap_text(input_text, wrap_line, wrap_end=None, debug=None):
    if wrap_end == None:
        wrap_end = wrap_line
    return wrap_line + "\n" + input_text + "\n" + wrap_end


def wrap_collapse(input_text, summary='Click to expand', debug=None):
    return f'<details>\n  <summary>{summary}</summary><br>\n\n{indent_text(input_text,2)}\n</details>\n\n'


def offer_instructions(language='en', debug=None):
    #console.print('\n')
    instructions_response = qs.confirm("Would you like instructions on how to use this tool?", default=False, style=questionary_style, qmark='   ?').ask()
    if instructions_response:
        console.print('\n')
        
        instruction_text = pkg_resources.read_text(instructions, f'instructions_{language}.txt')
        console.print(Panel(Padding(instruction_text, (2,4)), box=box.ROUNDED, style="edge"))
        console.print('\n')


def get_language_choice(languages=None, language=None, debug=None):
    _default_language='en'
    if languages is None or len(languages) == 0:
        if language is None:
            return _default_language
        else:
            return language

    if language in languages:
        return language

    console.print('\n')
    language_response = qs.select("Which language would you like to use? (only for instructions currently)",
        choices=[f'{languages[lang]:14} ({lang})' for lang in languages],
        style=questionary_style, qmark='   ?').ask()
    language_choice = language_response.split('(')[1][0:2]
    if debug:
        console.print(f'\nDEBUG: Language Choice: {language_choice}')
    return language_choice


def create_generated_by_message(override_message=None, override_format='%H:%M on %b %d %Y', debug=None):
    if override_message == None:
        msg = '_- generated at date/time using [Gather Up](https://github.com/nmstoker/gatherup) tool_ :gift:\n'
    else:
        msg = override_message
    dt = datetime.datetime.now()
    msg = msg.replace('date/time', dt.strftime(override_format), 1)
    return msg


def check_successful(debug=None):
    global QUIT
    console.print('\n')
    response = qs.select(
        "What would you like to do now?",
        choices=[
            'Quit',
            'Re-start'],
            style=questionary_style,
            qmark='   ?'
            ).ask()
    if response == 'Quit':
        QUIT = True
        return

def finished(debug=None):
    console.print('\n  Goodbye!  ', style='h1')
    console.print('\n')


def get_config_file():
    """Checks for existence of a config file in platform specific places, returning path if found."""
    config_file = ''
    # mimic code within confuse itself as seems not to have way to check this w/o creating directory
    configdirs = confuse.util.config_dirs()
    for confdir in configdirs:
        appdir = os.path.join(confdir, APPNAME)
        f = os.path.join(appdir, confuse.CONFIG_FILENAME)
        if os.path.isfile(f):
            config_file = f
            break
    return config_file


def set_config():
    return confuse.Configuration(APPNAME, __name__)

if __name__ == '__main__':
    gatherup()
