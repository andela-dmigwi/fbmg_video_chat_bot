''' Created by Migwi Ndung'u 
    @ The Samurai Community 2017
'''
import re
import jwt
import json
import random
import requests
from flask import redirect, g
from haikunator import Haikunator
from app.models import Transactions, Users
from app.kb import (reflections, call,
                    general, psychobabble)
from app.templates import *
from config import (fb_url, page_access_token, main_url,
                    JWT_ALGORITHM, JWT_SECRET)


params = {"access_token": page_access_token}
room_name = ''


class Utils(object):
    '''Class hold methods you to make a webrtc call and send
    via facebook messager'''

    def __init__(self):
        '''VideoCall holds set({'id'})'''
        self.video_call = set({})

    def tokenize(self, data):
        token = jwt.encode(data, JWT_SECRET, JWT_ALGORITHM)
        return token

    def user_contexts(self, type='remove'):
        if type is 'add':
            self.video_call.add(g.sender_id)
        else:
            self.video_call.discard(g.sender_id)

    def call_user(self, sender_id, recipient_id):
        sender_details = Transactions.query.filter_by(
            sender_id=sender_id).first()
        sender_data = ''
        recipient_data = ''

        # Check if a session created by sender exists
        if (sender_details.session):
            session = sender_details.session
        else:
            sender_data = {"user": recipient_id,
                           "session": Haikunator.haikunate()}
            Transactions(sender_data).save()

        try:
            recipient_data = {"user": recipient_id,
                              "session": session}
            # Push data to a database
            Transactions(recipient_data).save()
        except Exception:
            Transactions.rollback()

        recipient_token = self.tokenize(recipient_data)
        url = '{}/call/{}'.format(main_url, recipient_token)
        user = self.get_user_details(sender_id)

        if user == user_not_found:
            self.send_message(sender_id, message_text=something_wrong)
        else:
            template = join_call_template(user.name, url)
            self.send_message(recipient_id, template=template)

            sender_token = self.tokenize(sender_data)
            return redirect('/call/{}'.format(sender_token))

    def send_message(self, recipient_id, message_text=None, template=None):
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }

        if template:
            data['message'] = template

        data = json.dumps(data)
        url = "{}/me/messages".format(fb_url)
        response = requests.post(url, params=params,
                                 headers=json_headers, data=data)
        if response.status_code != 200:
            print('Error Code 1:', response.json(),
                  '\n User_id: ', recipient_id)

    def get_user_details(self, user_id):
        url = "{}/{}".format(fb_url, user_id)
        response = requests.get(url, params=params)
        if 'error' in response:
            print('Error Code 2:', response.json())
            return user_not_found
        return response.json()

    def reflect(self, fragment):
        tokens = fragment.lower().split()
        for i, token in enumerate(tokens):
            if token in reflections:
                tokens[i] = reflections[token]
        return ' '.join(tokens)

    def analyze(self, statement, matching_statement):
        for pattern, responses in matching_statement:
            match = re.match(pattern, statement.rstrip(".!"))
            if match:
                response = random.choice(responses)
                return response.format(
                    *[self.reflect(g) for g in match.groups()])
        else:
            return ''

    def match_response(self, text_message):
        options = [call, psychobabble, general]
        response = ''
        for item in options:
            response = self.analyze(text_message, item)
            if re.match(r'(.*call.*)', text_message):
                self.user_contexts(type='add')
            if response:
                return response
        else:
            # This should happen if something goes wrong
            self.user_contexts()
            print('Error Code 3: *********')
            return something_wrong

    def make_video_call(self, sender_id, text_message):
        matched_users = Users.query.filter(
            Users.name.contains(text_message),
            Users.fb_id != sender_id
        ).all()
        if matched_users and len(matched_users) == 1:
            # If user found is one create a call and join them
            self.user_contexts()
            recipient_id = matched_users[0].fb_id
            self.call_user(sender_id, recipient_id)

        elif matched_users and len(matched_users) < 6:
            # If 5 users, Generate quick replies template
            user_details = []
            for user in matched_users:
                profile_pic = default_profile_pic
                retrieved_user = self.get_user_details(user.fb_id)
                if 'profile_pic' in retrieved_user:
                    profile_pic = retrieved_user['profile_pic']
                user_details.append(
                    {"name": user.name,
                     "profile_pic": profile_pic}
                )
            else:
                template = quick_replies_template(user_details)
            self.send_message(sender_id, template=template)

        elif matched_users and len(matched_users) >= 6:
            # if more than six, Inform the user to try and
            # complete the other names as in Facebook
            self.send_message(sender_id, message_text=many_matches)
        else:
            # If user not found invite them to join Samurai Community
            # Send a share template to invite them to Samurai Community
            self.user_contexts()
            self.send_message(sender_id, message_text=SHARE_INVITE)
            self.send_message(sender_id, template=share_template())

    def postback(self, user_id, message_text):
        text = ''
        if message_text == 'SIGN_UP':
            text = self.user_registration(user_id)
        else:
            text = self.match_response(message_text)
        self.send_message(user_id, message_text=text)

    def user_registration(self, user_id):
        g.sender_id = user_id
        user = self.get_user_details(user_id)
        if user is user_not_found:
            return user_not_found
        else:
            try:
                name = "{} {}".format(user['first_name'], user['last_name'])
                Users(name=name, fb_id=user_id).save()
                return welcome_text
            except Exception:
                return self.match_response('Hello')

    def eliza_response(self, sender_id, text_message):
        g.sender_id = sender_id
        if sender_id in self.video_call:
            # Make a Video call
            self.make_video_call(sender_id, text_message)
        else:
            # Generate response using eliza
            # Return a message after matching the keys
            response = self.match_response(text_message)
            self.send_message(sender_id, message_text=response)
