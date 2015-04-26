#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json


from flask import Flask, request, render_template
from flask_hipchat_addon.addon import Addon, db, cache
from flask_hipchat_addon.clients import RoomClient
from flask_hipchat_addon.auth import tenant, sender
from flask_hipchat_addon.events import events
from closeio_api import Client as CloseIO_API


class CloseIOApi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    api_key = db.Column(db.Text, nullable=False)

    def __init__(self, tenant_id, api_key):
        self.tenant_id = tenant_id
        self.api_key = api_key


def on_uninstall(event):
    cache.delete_memoized(get_api_key, event['client'].id)
    close_io_api = CloseIOApi.query.filter_by(tenant_id=event['client'].id).first()
    db.session.delete(close_io_api)
    db.session.commit()


class CloseioAddon(Addon):

    def __init__(self, app, key=None, name=None, description=None,
                 allow_room=True, allow_global=False, scopes=None, vendor_name=None, vendor_url=None):

        super(CloseioAddon, self).__init__(app, key, name, description,
                                           allow_room, allow_global, scopes, vendor_name, vendor_url)

        with self.app.app_context():
            cache.clear()
            db.create_all()
        events.register_event("uninstall", on_uninstall)


app = Flask(__name__)

app.config.from_object('settings')

app.config.setdefault('SQLALCHEMY_DATABASE_URI', os.environ.get('DATABASE_URL'))

for name in ['HIPCHAT_ADDON_KEY',
             'HIPCHAT_ADDON_NAME',
             'HIPCHAT_ADDON_DESCRIPTION',
             'HIPCHAT_ADDON_VENDOR_URL',
             'HIPCHAT_ADDON_VENDOR_NAME',
             'HIPCHAT_ADDON_BASE_URL']:
    app.config.setdefault(name, os.environ.get(name))


addon = CloseioAddon(app=app, allow_global=True, scopes=['send_notification'])


@cache.memoize(timeout=3600)
def get_api_key(tenant_id):
    close_io_api = CloseIOApi.query.filter_by(tenant_id=tenant_id).first()
    return close_io_api.api_key


def get_lead_info(api, lead_id):
    lead = api.get('lead/'+lead_id,
                   data={'_fields': 'id,display_name,status_label,opportunities,contacts,organization_id'})
    return lead

def get_orga_info(api, orga_id):
    orga = api.get('organization/'+orga_id,
                   data={'_fields': 'id,currency_symbol'})
    return orga

LEAD_REGEXP = re.compile(ur'.*https://app\.close\.io\/lead\/(lead_[a-zA-Z0-9]+)', re.MULTILINE | re.UNICODE)


@addon.webhook(event='room_message', pattern='https:\/\/app\.close\.io\/lead\/lead_[a-zA-Z0-9]+')
def room_message_hook():
    data = json.loads(request.data)
    message = data['item']['message']['message']
    room_id = data['item']['room']['id']

    matched = re.match(LEAD_REGEXP, message)
    if matched:
        lead_id = matched.group(1)
        api = CloseIO_API(get_api_key(tenant.id))
        lead = get_lead_info(api, lead_id)
        if lead:
            orga = get_orga_info(api, lead['organization_id'])
            notification = render_template('lead.html', lead=lead, orga=orga)
            room_client = RoomClient(room_id)
            room_client.send_notification(notification)
    return '', 204


@addon.configure_page(methods=['GET'])
def configure_page(error=None, success=None):
    close_io_api = CloseIOApi.query.filter_by(tenant_id=tenant.id).first()
    api_key = ''
    if close_io_api:
        api_key = close_io_api.api_key
    return render_template('configure.html', token=tenant.sign_jwt(sender.id),
                           api_key=api_key, success=success), 200


@addon.configure_page(methods=['POST'])
def save_configuration():
    new_api_key = request.form.get('apikey')
    cache.delete_memoized(get_api_key, tenant.id)
    if new_api_key is not None:
        new_api_key = new_api_key.strip()
        close_io_api = CloseIOApi.query.filter_by(tenant_id=tenant.id).first()
        if not close_io_api:
            close_io_api = CloseIOApi(tenant.id, new_api_key)
        else:
            close_io_api.api_key = new_api_key
        db.session.add(close_io_api)
        db.session.commit()

    return configure_page(success='New key was saved')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    addon.run(host='0.0.0.0', port=port)
