#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json

from flask import Flask, request, render_template
from flask_hipchat_addon.addon import Addon, db
from flask_hipchat_addon.clients import RoomClient
from flask_hipchat_addon.auth import tenant, sender
from closeio_api import Client as CloseIO_API, APIError


class CloseIOApi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    api_key = db.Column(db.Text, nullable=False)

    def __init__(self, tenant_id, api_key):
        self.tenant_id = tenant_id
        self.api_key = api_key


app = Flask(__name__)
app.config.from_object('settings')
addon = Addon(app=app, allow_global=True, scopes=['send_notification'])

LEAD_REGEXP = re.compile(ur'.*(https://app\.close\.io\/lead\/)(lead_[a-zA-Z0-9]+)', re.MULTILINE | re.UNICODE)

@addon.webhook(event='room_message', pattern='https:\/\/app\.close\.io\/lead\/lead_[a-zA-Z0-9]+')
def room_message_hook():
    data = json.loads(request.data)
    message = data['item']['message']['message']
    room_id = data['item']['room']['id']

    matched = re.match(LEAD_REGEXP, message)
    if matched:
        lead_url = matched.group(1) + matched.group(2)
        lead_id = matched.group(2)
        api = CloseIO_API(app.config['CLOSE_IO_API_KEY'])
        resp = api.get('lead/'+lead_id, data={'_fields': 'id,display_name'})
        notification = '<a href="'+lead_url+'">'+lead_url+'</a><br/><b>'+resp['display_name']+'</b>'
        room_client = RoomClient(room_id)
        room_client.send_notification(notification)
    return '', 204

@addon.configure_page(methods=['GET'])
def configure_page(error=None, success=None):
    app.logger.debug('tenant: %s', tenant)
    close_io_api = CloseIOApi.query.filter_by(tenant_id=tenant.id).first()
    api_key = ''
    if close_io_api:
        api_key = close_io_api.api_key
    return render_template('configure.html', token=tenant.sign_jwt(sender.id),
                           api_key=api_key, success=success), 200

@addon.configure_page(methods=['POST'])
def save_configuration():
    app.logger.debug('tenant: %s', tenant)
    new_api_key = request.form['api_key'].strip()
    close_io_api = CloseIOApi.query.filter_by(tenant_id=tenant.id).first()
    if not close_io_api:
        close_io_api = CloseIOApi(tenant.id, new_api_key)
    else:
        close_io_api.api_key = new_api_key
    db.session.add(close_io_api)
    db.session.commit()

    return configure_page(success='New key saved')


if __name__ == '__main__':
    addon.run(debug=True)