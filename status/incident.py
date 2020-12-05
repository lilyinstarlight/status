import datetime
import os
import os.path
import re
import subprocess
import textwrap

import dateutil.parser
import dateutil.tz


__all__ = ['get_filename', 'get_all', 'get', 'create', 'modify']


def slugify(text):
    return re.sub('^-+|-+$', '', re.sub('--+', '-', re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-').replace('.', '-'))))


def extract_title(incident_file):
    title = incident_file.readline()
    while title and not title.strip():
        title = incident_file.readline()

    title = title.strip()

    if title[0] == '#':
        title = title[1:]
    else:
        incident_file.readline()

    title = title.strip()

    return title


def extract_date(incident_file, timezone=None):
    pos = incident_file.tell()

    line = incident_file.readline()
    while line and not line.strip():
        line = incident_file.readline()

    date = None

    if not date and line.startswith('Date:'):
        try:
            date = dateutil.parser.isoparse(line[5:].strip()).astimezone(dateutil.tz.gettz(timezone))
        except ValueError:
            pass

    if not date:
        date = datetime.datetime.fromtimestamp(os.fstat(incident_file.fileno()).st_mtime, datetime.timezone.utc).astimezone(dateutil.tz.gettz(timezone))

        incident_file.seek(pos)

    return date


def extract_status(incident_file):
    pos = incident_file.tell()

    line = incident_file.readline()
    while line and not line.strip():
        line = incident_file.readline()

    status = None

    if not status and line.startswith('Status:'):
        status = line[7:].strip()

    if not status:
        status = 'up'

        incident_file.seek(pos)

    return status


def extract_affected(incident_file):
    pos = incident_file.tell()

    line = incident_file.readline()
    while line and not line.strip():
        line = incident_file.readline()

    affected = None

    if not affected and line.startswith('Affected:'):
        affected = []

        prevline = incident_file.tell()
        line = incident_file.readline()
        while line and not line.strip():
            line = incident_file.readline()

        while line:
            if not line.strip():
                line = incident_file.readline()
                continue

            if not line.startswith('*'):
                incident_file.seek(prevline)
                break

            affected.append(line[1:].strip().lower())

            prevline = incident_file.tell()
            line = incident_file.readline()

    if affected is None:
        affected = []

        incident_file.seek(pos)

    return affected


def extract_content(incident_file):
    return incident_file.read()


def make_name(directory, date, title):
    name = date.strftime('%Y-%m-%d') + '-' + slugify(title)

    num = 0
    while os.path.exists(os.path.join(directory, name + '.md')):
        num += 1
        name = date.strftime('%Y-%m-%d') + '-' + slugify(title) + '-' + str(num)

    return name


def get_filename(directory, name):
    return os.path.join(directory, name + '.md')


def get_all(directory, timezone=None):
    return sorted([get(directory, filename[:-3], timezone) for filename in os.listdir(directory) if filename.endswith('.md')], key=(lambda incident: incident['date']), reverse=True)


def get(directory, name, timezone=None):
    with open(os.path.join(directory, name + '.md'), 'r') as incident_file:
        title = extract_title(incident_file)
        date = extract_date(incident_file, timezone)
        status = extract_status(incident_file)
        affected = extract_affected(incident_file)
        content = extract_content(incident_file)

    return {
        'name': name,
        'title': title,
        'date': date,
        'status': status,
        'affected': affected,
        'content': content,
    }


def rename(directory, name):
    incident = get(directory, name)
    new_name = make_name(directory, incident['date'], incident['title'])

    if name != new_name:
        os.rename(os.path.join(directory, name + '.md'), os.path.join(directory, new_name + '.md'))

    return new_name


def create(directory, *, name=None, date=None, title='', status='up', affected=None, content='', timezone=None):
    if not date:
        date = datetime.datetime.now().astimezone(dateutil.tz.gettz(timezone))

    if not name:
        name = date.strftime('%Y-%m-%d') + '-' + slugify(title)

        num = 0
        while os.path.exists(os.path.join(directory, name + '.md')):
            num += 1
            name = date.strftime('%Y-%m-%d') + '-' + slugify(title) + '-' + str(num)

    date_formatted = date.isoformat(timespec='minutes')
    affected_formatted = '\nAffected:\n' + ''.join(f'* {service}\n' for service in affected) + '\n' if affected else ''

    with open(os.path.join(directory, name + '.md'), 'w') as incident_file:
        incident_file.write(textwrap.dedent(f'''
        # {title}

        Date: {date_formatted}
        Status: {status}
        {affected_formatted}
        {content}
        ''').lstrip())

    return name


def modify(directory, name, *, date=None, title=None, status=None, affected=None, content='', timezone=None):
    incident = get(directory, name)

    if not date:
        date = incident['date']
    if not title:
        title = incident['title']
    if not status:
        status = incident['status']
    if not affected:
        affected = incident['affected']

    return create(directory, name=incident['name'], date=date, title=title, status=status, affected=affected, content=(incident['content'] + '\n' + content if content else ''), timezone=None)
