import datetime
import html
import json
import os.path

import markdown

import feedgen.feed


__all__ = ['generate_html', 'generate_json', 'generate_atom', 'generate_rss']


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


def generate_html(config, now, services, statuses, incidents, *, template_directory=None):
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

    with open(os.path.join(template_directory, 'none.html'), 'r') as template_file:
        none_template = template_file.read().rstrip('\r\n')

    services_html = []

    for service, status in statuses.items():
        services_html.append(service_template.format(name=html.escape(service), title=html.escape(services[service]['title']), link=html.escape(services[service]['link']), description=html.escape(services[service]['description']), status=html.escape(status), pretty=html.escape(pretty_statuses[status]), affected=('affected' if any(service in incident['affected'] for incident in incidents if incident['status'] != 'up') else '')))

    if not services_html:
        services_html.append(none_template)

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

        incidents_html.append(incident_template.format(name=html.escape(incident['name']), title=render_title(incident['title']), datetime=incident['date'].isoformat(timespec='milliseconds'), date=html.escape(incident['date'].strftime('%Y-%m-%d %H:%M %Z')), updatedtime=incident['updated'].isoformat(timespec='milliseconds'), updated=html.escape(incident['updated'].strftime('%Y-%m-%d %H:%M %Z')), status=html.escape(incident['status'] if incident['status'] in pretty_statuses else ''), pretty=html.escape(pretty_statuses.get(incident['status'], incident['status'])), content=render(incident['content']), affected=affected_html))

    if not incidents_html:
        incidents_html.append(none_template)

    return status_template.format(title=config['title'], nowtime=now.isoformat(timespec='milliseconds'), now=html.escape(now.strftime('%Y-%m-%d %H:%M %Z')), services='\n'.join(services_html), incidents='\n'.join(incidents_html))


def generate_json(config, now, services, statuses, incidents):
    services_json = services.copy()
    incidents_json = incidents[:]

    for info in services_json.values():
        del info['id']

    for incident in incidents_json:
        incident['date'] = incident['date'].isoformat(timespec='milliseconds')
        incident['updated'] = incident['updated'].isoformat(timespec='milliseconds')

    return json.dumps({'last_updated': now.isoformat(timespec='milliseconds'), 'services': {service: {**info, 'status': statuses[service]} for service, info in services_json.items()}, 'incidents': incidents_json}, indent=2) + '\n'


def create_feed(config, now, incidents):
    fg = feedgen.feed.FeedGenerator()

    fg.id('incidents')
    fg.title(config['title'])
    fg.subtitle(config['title'] + ' - Incidents')
    fg.link(href='/')

    if 'link' in config:
        fg.link(config['link'])

    if 'logo' in config:
        fg.logo(config['logo'])

    updated = None

    for incident in incidents[::-1]:
        fe = fg.add_entry()

        fe.title(incident['title'])
        fe.published(incident['date'])
        fe.updated(incident['updated'])
        fe.content('Status: {status}\n{affected}\n{content}'.format(status=incident['status'], affected=('\nAffected:\n' + ''.join(f'* {service}\n' for service in incident['affected']) if incident['affected'] else ''), content=incident['content']), type='text')

        fe.id(incident['name'])

        if not updated or incident['updated'] > updated:
            updated = incident['updated']

    fg.updated(updated)

    return fg


def generate_atom(config, now, incidents):
    return create_feed(config, now, incidents).atom_str(pretty=True)


def generate_rss(config, now, incidents):
    return create_feed(config, now, incidents).rss_str(pretty=True)
