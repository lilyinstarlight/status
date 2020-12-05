import argparse
import configparser
import datetime
import os
import os.path
import subprocess
import sys
import tempfile

import dateutil.parser
import dateutil.tz

import status.generate
import status.grafana
import status.incident


__all__ = ['main']


def main():
    argparser = argparse.ArgumentParser(description='another static status page generator')

    argparser.add_argument('-c', '--config', dest='config', required=True, metavar='CONFIG.cfg', help='configuration file describing grafana connection and services')
    argparser.add_argument('-d', '--directory', dest='directory', required=True, help='directory containing incident info')
    argparser.add_argument('-z', '--timezone', dest='timezone', help='alternative timezone for output')

    commands = argparser.add_subparsers(dest='command')

    command_run = commands.add_parser('run', help='generate status page')
    command_run.add_argument('-o', '--output', dest='output', help='output directory (generates index.html, status.json, and feed.xml)')
    command_run.add_argument('-t', '--template', dest='template', help='input template directory')
    command_run.add_argument('-i', '--incident-days', dest='days', type=int, default=7, help='number of days of resolved incidents to show')

    command_new_incident = commands.add_parser('new-incident', help='create new incident from arguments (markdown content can be piped to stdin)')
    command_new_incident.add_argument('--date', dest='date', help='date of incident')
    command_new_incident.add_argument('--title', dest='title', help='title of incident')
    command_new_incident.add_argument('--status', dest='status', choices=['up', 'down', 'maintenance', 'unknown'], help='incident status')
    command_new_incident.add_argument('--affected', dest='affected', nargs='*', help='services affected (specify multiple times per service)')
    command_new_incident.add_argument('name', nargs='?', help='slug name for incident')

    command_edit_incident = commands.add_parser('edit-incident', help='modify existing incident from arguments (markdown content can be piped to stdin)')
    command_edit_incident.add_argument('--date', dest='date', help='date of incident')
    command_edit_incident.add_argument('--title', dest='title', help='title of incident')
    command_edit_incident.add_argument('--status', dest='status', choices=['up', 'down', 'maintenance', 'unknown'], help='incident status')
    command_edit_incident.add_argument('--affected', dest='affected', nargs='*', help='services affected (specify multiple times per service)')
    command_edit_incident.add_argument('name', help='slug name for incident')

    args = argparser.parse_args()
    if not args.command:
        argparser.print_usage()
        sys.exit()

    config = configparser.ConfigParser()
    config.read(args.config)

    services = {section: config[section] for section in config.sections() if section != 'api'}

    os.makedirs(args.directory, exist_ok=True)

    if args.command == 'run':
        statuses = status.grafana.check(config['api']['base'], config['api']['key'], services)
        incidents = status.incident.get_all(args.directory, args.timezone)

        now = datetime.datetime.now().astimezone(dateutil.tz.gettz(args.timezone))

        for incident in incidents[:]:
            if args.days and incident['date'] >= (now - datetime.timedelta(days=args.days)):
                    continue

            if incident['status'] == 'up':
                incidents.remove(incident)

        output = args.output or os.getcwd()
        os.makedirs(output, exist_ok=True)

        with open(os.path.join(output, 'index.html'), 'w') as output_html:
            output_html.write(status.generate.generate_html(now, services, statuses, incidents, template_directory=args.template))

        with open(os.path.join(output, 'status.json'), 'w') as output_json:
            output_json.write(status.generate.generate_json(now, services, statuses, incidents))
    elif args.command == 'new-incident':
        info = {}
        if args.date:
            info['date'] = dateutil.parser.isoparse(args.date).astimezone(dateutil.tz.gettz(args.timezone))
        if args.title:
            info['title'] = args.title
        if args.status:
            info['status'] = args.status
        if args.affected:
            info['affected'] = args.affected
        if args.name:
            info['name'] = args.name

        if sys.stdin.isatty():
            name = status.incident.create(args.directory, **info, timezone=args.timezone)
            subprocess.run([os.environ.get('EDITOR', 'vi'), status.incident.get_filename(args.directory, name)])
            status.incident.rename(args.directory, name)
        else:
            status.incident.create(args.directory, **info, content=sys.stdin.read(), timezone=args.timezone)
    elif args.command == 'edit-incident':
        info = {}
        if args.date:
            info['date'] = dateutil.parser.isoparse(args.date).astimezone(dateutil.tz.gettz(args.timezone))
        if args.title:
            info['title'] = args.title
        if args.status:
            info['status'] = args.status
        if args.affected:
            info['affected'] = args.affected

        if sys.stdin.isatty():
            name = status.incident.modify(args.directory, args.name, **info, timezone=args.timezone)
            subprocess.run([os.environ.get('EDITOR', 'vi'), status.incident.get_filename(args.directory, name)])
        else:
            status.incident.modify(args.directory, args.name, **info, content=sys.stdin.read(), timezone=args.timezone)
    else:
        argparser.print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
