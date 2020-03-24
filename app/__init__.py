from flask import Flask
from flask_cors import CORS
#from flask_basicauth import BasicAuth
from config import Config

app = Flask(__name__)
CORS(app, resources=r'/api/*')
app.config.from_object(Config)

from app import routes
