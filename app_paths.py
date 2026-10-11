"""Per-user writable paths, independent of the installation/launch folder."""
import os
import sys


def application_data_dir():
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser(r'~\AppData\Local')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'RaahiScraper')


def default_output_folder():
    return os.path.join(application_data_dir(), 'Exports')
