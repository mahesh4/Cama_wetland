import pymongo
import json
import os
from sshtunnel import SSHTunnelForwarder


class DbConnect:

    def __init__(self):
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        with open(file_path) as f:
            config = json.load(f)
            f.close()
        # SSH / Mongo Configuration #
        self.MONGO_SERVER = SSHTunnelForwarder(
            (config["MONGO_IP"], 22),
            ssh_username=config["SSH_USERNAME"],
            ssh_pkey=config["SSH_KEYFILE"],
            remote_bind_address=('localhost', 27017)
        )
        self.MONGO_CLIENT = None

    def connect_db(self):
        try:
            # open the SSH tunnel to the mongo server
            self.MONGO_SERVER.start()
            # open mongo connection
            self.MONGO_CLIENT = pymongo.MongoClient('localhost', self.MONGO_SERVER.local_bind_port)
        except Exception as e:
            print('cannot connect')
            raise e

    def get_connection(self):
        return self.MONGO_CLIENT

    def disconnect_db(self):
        try:
            # close mongo connection
            self.MONGO_CLIENT.close()
            # close the SSH tunnel to the mongo server
            self.MONGO_SERVER.close()
            self.MONGO_CLIENT = None
            print('closed all the connections')
        except Exception as e:
            print('cannot disconnect')
            raise e



