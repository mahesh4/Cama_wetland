import pymongo
import json
import os
from sshtunnel import SSHTunnelForwarder

USE_SSH = False


class DbConnect:

    def __init__(self):
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        self.CONFIG = None
        with open(file_path) as f:
            self.CONFIG = json.load(f)
            f.close()

        self.MONGO_SERVER = None
        self.MONGO_CLIENT = None

    def connect_db(self):
        try:
            if USE_SSH:
                # SSH / Mongo Configuration #
                self.MONGO_SERVER = SSHTunnelForwarder(
                    (self.CONFIG["MONGO_IP"], 22),
                    ssh_username=self.CONFIG["SSH_USERNAME"],
                    ssh_pkey=self.CONFIG["SSH_KEYFILE"],
                    remote_bind_address=('localhost', 27017)
                )
                # open the SSH tunnel to the mongo server
                self.MONGO_SERVER.start()
                # open mongo connection
                self.MONGO_CLIENT = pymongo.MongoClient('localhost', self.MONGO_SERVER.local_bind_port)
            else:
                self.MONGO_CLIENT = pymongo.MongoClient(host=self.CONFIG["MONGO_IP"])

        except Exception as e:
            print('cannot connect')
            raise e

    def get_connection(self):
        return self.MONGO_CLIENT

    def disconnect_db(self):
        try:
            # close mongo connection
            self.MONGO_CLIENT.close()
            if USE_SSH:
                # close the SSH tunnel to the mongo server
                self.MONGO_SERVER.close()
            self.MONGO_CLIENT = None
            print('closed all the connections')
        except Exception as e:
            print('cannot disconnect')
            raise e
