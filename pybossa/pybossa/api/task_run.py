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
from pybossa.util import get_user_id_or_ip, current_app
from pybossa.core import task_repo, sentinel
from pybossa.uploader.s3_uploader import s3_upload_from_string
from pybossa.gig_utils import json_traverse
from pybossa.uploader.s3_uploader import s3_upload_file_storage
from datetime import datetime


class TaskRunAPI(APIBase):

    """Class API for domain object TaskRun."""

    DEFAULT_DATETIME = '1900-01-01T00:00:00.000000'
    DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

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
        self._add_timestamps(taskrun, task, sentinel.master)

    def _forbidden_attributes(self, data):
        for key in data.keys():
            if key in self.reserved_keys:
                raise BadRequest("Reserved keys in payload")

    def _add_user_info(self, taskrun):
        if current_user.is_anonymous():
            taskrun.user_ip = request.remote_addr
        else:
            taskrun.user_id = current_user.id

    def _add_timestamps(self, taskrun, task, redis_conn):
        finish_time = datetime.now().isoformat()
        # /cachePresentedTime API only caches when there is a user_id
        usr = taskrun.user_id or None
        if redis_conn is not None and usr is not None and task.id:
            presented_time_key = 'pybossa:user:{0}:task_id:{1}:presented_time_key' \
                    .format(usr, task.id)
            presented_time = redis_conn.get(presented_time_key)
            created = self._validate_datetime(presented_time)
        else:
            current_app.logger.info('TASKRUN_API_LOG: Cannot cache presented_time - redis_conn: {0}, user: {1}, task.id {2}'.format(redis_conn, usr, task.id))
            created = datetime.strptime(self.DEFAULT_DATETIME, self.DATETIME_FORMAT)

        # sanity check
        if created < finish_time:
            taskrun.created = created
            taskrun.finish_time = finish_time
        else:
            current_app.logger.info('TASKRUN_API_LOG: Creation Time {0} cannot be after Finished Time {1}'.format(created, finish_time))
            # return an arbitrary valid timestamp so that answer can be submitted
            created = datetime.strptime(self.DEFAULT_DATETIME, self.DATETIME_FORMAT)
            taskrun.created = created.isoformat()
            taskrun.finish_time = finish_time

        # delete cached time
        if redis_conn.get(presented_time_key):
            redis_conn.delete(presented_time_key)

    def _validate_datetime(self, timestamp):
        try:
            timestamp = datetime.strptime(timestamp, self.DATETIME_FORMAT)
        except:
            current_app.logger.info('TASKRUN_API_LOG: Invalid datetime: {0}'.format(timestamp))
            # return an arbitrary valid timestamp so that answer can be submitted
            timestamp = datetime.strptime(self.DEFAULT_DATETIME, self.DATETIME_FORMAT)
        return timestamp.isoformat()


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
