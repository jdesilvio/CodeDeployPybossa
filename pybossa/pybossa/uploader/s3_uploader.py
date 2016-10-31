import boto
from flask import current_app as app
from werkzeug.utils import secure_filename


def s3_upload_from_string(string, filename, headers=None, directory=""):

    if directory:
        upload_dir = "/".join([app.config["S3_UPLOAD_DIRECTORY"], directory])
    else:
        upload_dir = app.config["S3_UPLOAD_DIRECTORY"]

    filename = secure_filename(filename)
    # Connect to S3 and upload file.
    conn = boto.connect_s3(app.config["S3_KEY"], app.config["S3_SECRET"])
    b = conn.get_bucket(app.config["S3_BUCKET"])

    key = b.new_key("/".join([upload_dir, filename]))
    key.set_contents_from_string(string, headers=headers)

    return key.generate_url(0).split('?', 1)[0]


def s3_upload_file_obj(source_file, directory=""):
    """ Uploads FileStorage Object to Amazon S3
        Expects following app.config attributes to be set:
            S3_KEY              :   S3 API Key
            S3_SECRET           :   S3 Secret Key
            S3_BUCKET           :   What bucket to upload to
            S3_UPLOAD_DIRECTORY :   Which S3 Directory.
    """

    if directory:
        upload_dir = "/".join([app.config["S3_UPLOAD_DIRECTORY"], directory])
    else:
        upload_dir = app.config["S3_UPLOAD_DIRECTORY"]

    filename = secure_filename(source_file.filename)
    headers = {"Content-Type": source_file.content_type}
    # Connect to S3 and upload file.
    conn = boto.connect_s3(app.config["S3_KEY"], app.config["S3_SECRET"])
    b = conn.get_bucket(app.config["S3_BUCKET"])

    key = b.new_key("/".join([upload_dir, filename]))
    key.set_contents_from_file(source_file.stream, headers=headers)

    return key.generate_url(0).split('?', 1)[0]
