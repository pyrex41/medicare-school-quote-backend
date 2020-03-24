import os

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    CSG_TOKEN = os.environ.get('CSG_TOKEN') or '9c983c732ce0d20fdbad01ff67e9c09f2a3c42a7066e5a79596a83b7775d6a9a' #'f74c9ce5bbd573526c958605b04ce92f45d8264548b173b6417129d8f8a55689'
    API_KEY = os.environ.get('API_KEY') or '2150e5ea35698640582ef9c511c8090210b2f7a0f8e53672094b8e5d3c7f9275'
