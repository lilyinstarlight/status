import datetime
import html
import json
import os.path

import markdown


__all__ = ['generate_html', 'generate_json']


pretty_statuses = {
    'up': 'Operational',
    'down': 'Unavailable',
    'maintenance': 'Maintenance',
    'unknown': 'Unknown',
}


def render(content):
    return markdown.markdown(content, extensions=['extra', 'codehilite', 'sane_lists', 'smarty'], output_format='xhtml')


def render_title(title):
    rendered = render(title)

    if rendered.startswith('<p>') and rendered.endswith('</p>'):
        rendered = rendered[3:-4]

    return rendered


def generate_html(now, services, statuses, incidents, *, template_directory=None):
    if not template_directory:
        template_directory = os.path.join(os.path.dirname(__file__), 'html')

    with open(os.path.join(template_directory, 'index.html'), 'r') as template_file:
        status_template = template_file.read()

    with open(os.path.join(template_directory, 'service.html'), 'r') as template_file:
        service_template = template_file.read().rstrip('\r\n')

    with open(os.path.join(template_directory, 'incident.html'), 'r') as template_file:
        incident_template = template_file.read().rstrip('\r\n')

    with open(os.path.join(template_directory, 'affected.html'), 'r') as template_file:
        affected_template = template_file.read().rstrip('\r\n')

    with open(os.path.join(template_directory, 'affected_service.html'), 'r') as template_file:
        affected_service_template = template_file.read().rstrip('\r\n')

    services_html = []

    for service, status in statuses.items():
        services_html.append(service_template.format(name=html.escape(service), title=html.escape(services[service]['title']), link=html.escape(services[service]['link']), description=html.escape(services[service]['description']), status=html.escape(status), pretty=html.escape(pretty_statuses[status]), affected=('affected' if any(service in incident['affected'] for incident in incidents if incident['status'] != 'up') else '')))

    if not services_html:
        services_html.append('<p>None</p>')

    incidents_html = []

    for incident in incidents:
        affected_service_html = []
        for service in incident['affected']:
            if service not in services:
                continue

            affected_service_html.append(affected_service_template.format(name=html.escape(service), title=html.escape(services[service]['title']), link=html.escape(services[service]['link'])))

        if affected_service_html:
            affected_html = '\n' + affected_template.format(services='\n'.join(affected_service_html))
        else:
            affected_html = ''

        incidents_html.append(incident_template.format(name=html.escape(incident['name']), title=render_title(incident['title']), datetime=incident['date'].isoformat(timespec='milliseconds'), date=html.escape(incident['date'].strftime('%Y-%m-%d %H:%M %Z')), status=html.escape(incident['status'] if incident['status'] in pretty_statuses else ''), pretty=html.escape(pretty_statuses.get(incident['status'], incident['status'])), content=render(incident['content']), affected=affected_html))

    if not incidents_html:
        incidents_html.append('<p>None</p>')

    return status_template.format(nowtime=now.isoformat(timespec='milliseconds'), now=html.escape(now.strftime('%Y-%m-%d %H:%M %Z')), services='\n'.join(services_html), incidents='\n'.join(incidents_html))


def generate_json(now, services, statuses, incidents):
    services_json = services.copy()
    incidents_json = incidents[:]

    for info in services_json.values():
        del info['id']

    for incident in incidents_json:
        incident['date'] = incident['date'].isoformat(timespec='milliseconds')

    return json.dumps({'last_updated': now.isoformat(timespec='milliseconds'), 'services': {service: {**info, 'status': statuses[service]} for service, info in services_json.items()}, 'incidents': incidents_json}, indent=2) + '\n'
