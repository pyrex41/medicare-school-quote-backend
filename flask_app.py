from app import app as application

if __name__ == "--main__":
  application.run(ssl_context='adhoc')
