from uuid import uuid4
import boto
import os.path
from flask import current_app as app


# from werkzeug.utils import secure_filename


def s3_upload_from_string(string, filename, headers=None, upload_dir=None):
    if upload_dir is None:
        upload_dir = app.config["S3_UPLOAD_DIRECTORY"]

    # Connect to S3 and upload file.
    conn = boto.connect_s3(app.config["S3_KEY"], app.config["S3_SECRET"])
    b = conn.get_bucket(app.config["S3_BUCKET"])

    key = b.new_key("/".join([upload_dir, filename]))
    key.set_contents_from_string(string, headers=headers)

    return key.generate_url(0).split('?', 1)[0]


def s3_upload(source_file, upload_dir=None):
    """ Uploads WTForm File Object to Amazon S3
        Expects following app.config attributes to be set:
            S3_KEY              :   S3 API Key
            S3_SECRET           :   S3 Secret Key
            S3_BUCKET           :   What bucket to upload to
            S3_UPLOAD_DIRECTORY :   Which S3 Directory.
    """

    if upload_dir is None:
        upload_dir = app.config["S3_UPLOAD_DIRECTORY"]

    source_filename = source_file.data.filename

    # Connect to S3 and upload file.
    conn = boto.connect_s3(app.config["S3_KEY"], app.config["S3_SECRET"])
    b = conn.get_bucket(app.config["S3_BUCKET"])

    key = b.new_key("/".join([upload_dir, source_filename]))
    key.set_contents_from_string(source_file.data.read())

    return key.generate_url(0).split('?', 1)[0]
