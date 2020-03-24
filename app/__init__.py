from flask import Flask
from flask_cors import CORS
from config import Config

app = CORS(Flask(__name__))
app.config.from_object(Config)

from app import routes
