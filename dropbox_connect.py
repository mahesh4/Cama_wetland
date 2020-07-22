import dropbox
import glob
import os.path
import json
from dropbox.files import WriteMode
from db_connect import DbConnect


class DropBox:
    def __init__(self):
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        with open(file_path) as f:
            config = json.load(f)
            f.close()
        access_token = config["DROPBOX_ACCESS_TOKEN"]
        self.DBX = dropbox.Dropbox(access_token)
        self.DB = DbConnect()
        self.BASE_PATH = config["CAMA_BASE_PATH"]

    def create_folder(self, folder_name):
        try:
            # Inserting the folder into Dropbox
            folder = "/" + folder_name
            self.DBX.files_create_folder_v2(folder, autorename=False)
        except Exception as e:
            raise e

    def upload_output(self):
        try:
            self.DB.connect_db()
            mongo_client = self.DB.get_connection()
            folder_collection = mongo_client["output"]["folder"]
            output_path = os.path.join(self.BASE_PATH, "out", "hamid")
            folder = folder_collection.find_one({"status": "running"})
            if folder is None:
                raise Exception("Record doesn't exist")
            if not self.folder_exists(folder["folder_name"]):
                raise Exception("Folder doesn't exist in dropbox")
            # Uploading the results
            folder_name = "/" + folder["folder_name"]
            for filename in glob.glob(os.path.join(output_path, '*.bin')):
                with open(filename, 'rb') as fp:
                    self.DBX.files_upload(fp.read(), folder_name + "/" + filename.split("/")[-1], mode=WriteMode("overwrite"))
                    fp.close()
            # updating database to set status to completed
            folder_collection.update({"_id": folder["_id"]}, {"$set": {"status": "completed"}})
        except Exception as e:
            raise e
        finally:
            self.DB.disconnect_db()

    def folder_exists(self, folder_name):
        try:
            metadata = self.DBX.files_get_metadata("/" + folder_name)
            if isinstance(metadata, dropbox.files.FolderMetadata):
                return True
            else:
                return False
        except Exception as e:
            return False

    def download_file(self, folder_name, file_name):
        try:
            file_path = "/" + folder_name + "/" + file_name
            temp_dir = os.path.join(os.getcwd(), "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            if not os.path.exists(os.path.join(os.getcwd(), "temp", folder_name)):
                os.mkdir(os.path.join(os.getcwd(), "temp", folder_name))

            self.DBX.files_download_to_file(os.path.join(os.getcwd(), "temp", folder_name, file_name), file_path)
            print("downloaded ", file_name)
        except Exception as e:
            raise e

    def delete_folder(self, folder_name):
        try:
            path = "/" + folder_name
            self.DBX.files_delete_v2(path)
        except Exception as e:
            raise e


if __name__ == "__main__":
    dropbox_obj = DropBox()
    dropbox_obj.upload_output()
