# -*- coding: utf8 -*-
# This file is part of PyBossa.
#
# Copyright (C) 2014 SF Isle of Man Limited
#
# PyBossa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyBossa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PyBossa.  If not, see <http://www.gnu.org/licenses/>.
"""
PyBossa api module for exposing domain object TaskRun via an API.

This package adds GET, POST, PUT and DELETE methods for:
    * task_runs

"""
from flask import request
from flask.ext.login import current_user
from pybossa.model.task_run import TaskRun
from werkzeug.exceptions import Forbidden, BadRequest

from api_base import APIBase
from pybossa.util import get_user_id_or_ip
from pybossa.core import task_repo, sentinel
from pybossa.uploader.s3_uploader import s3_upload_from_string
from pybossa.gig_utils import json_traverse
from pybossa.uploader.s3_uploader import s3_upload_file_storage
from datetime import datetime

class TaskRunAPI(APIBase):

    """Class API for domain object TaskRun."""

    __class__ = TaskRun
    reserved_keys = set(['id', 'created', 'finish_time'])

    def _preprocess_post_data(self, data):
        task_id = data['task_id']
        project_id = data['project_id']
        user_id = current_user.id
        info = data['info']
        path = "{0}/{1}/{2}".format(project_id, task_id, user_id)
        _upload_files_from_json(info, path)
        _upload_files_from_request(info, request.files, path)

    def _update_object(self, taskrun):
        """Update task_run object with user id or ip."""
        task = task_repo.get_task(taskrun.task_id)

        # validate the task and project for that taskrun are ok
        if task is None:  # pragma: no cover
            raise Forbidden('Invalid task_id')
        if task.project_id != taskrun.project_id:
            raise Forbidden('Invalid project_id')
        if _check_task_requested_by_user(taskrun, sentinel.master) is False:
            raise Forbidden('You must request a task first!')

        # validate and modify taskrun attributes
        self._add_user_info(taskrun)
        self._add_created_timestamp(taskrun, task)
        self._add_finish_timestamp(taskrun, task)

    def _forbidden_attributes(self, data):
        for key in data.keys():
            if key in self.reserved_keys:
                raise BadRequest("Reserved keys in payload")

    def _add_user_info(self, taskrun):
        if current_user.is_anonymous():
            taskrun.user_ip = request.remote_addr
        else:
            taskrun.user_id = current_user.id

    def _add_created_timestamp(self, taskrun, task):
        taskrun.created = _validate_datetime(taskrun.info.pop('start_time'))

    def _add_finish_timestamp(self, taskrun, task):
        taskrun.finish_time = _validate_datetime(taskrun.info.pop('end_time'))



def _check_task_requested_by_user(taskrun, redis_conn):
    user_id_ip = get_user_id_or_ip()
    usr = user_id_ip['user_id'] or user_id_ip['user_ip']
    key = 'pybossa:task_requested:user:%s:task:%s' % (usr, taskrun.task_id)
    task_requested = bool(redis_conn.get(key))
    if user_id_ip['user_id'] is not None:
        redis_conn.delete(key)
    return task_requested

def _upload_files_from_json(task_run_info, upload_path):
    def func(obj, key, value):
        if key.endswith('__upload_url'):
            filename = value.get('filename')
            content = value.get('content')
            if filename is None or content is None:
                return True
            out_url = s3_upload_from_string(content, filename,
                                            directory=upload_path)
            obj[key] = out_url
            return False
    json_traverse(task_run_info, func)


def _upload_files_from_request(task_run_info, files, upload_path):
    for key in files:
        if not key.endswith('__upload_url'):
            raise BadRequest("File upload field should end in __upload_url")
        file_obj = request.files[key]
        s3_url = s3_upload_file_storage(file_obj, directory=upload_path)
        task_run_info[key] = s3_url

def _validate_datetime(timestamp):
    try:
        timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
        return timestamp.isoformat()
    except ValueError:
        raise ValueError("Incorrect data format")
