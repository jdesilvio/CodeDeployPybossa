# -*- coding: utf8 -*-
# This file is part of PyBossa.
#
# Copyright (C) 2015 SciFabric LTD.
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
PyBossa api module for exposing domain object TaskRun for completed tasks via an API.

This package adds GET methods for:
    * task_runs

"""
from flask import request
from flask.ext.login import current_user
from pybossa.model.task_run import TaskRun
from pybossa.model.completed_task_run import CompletedTaskRun
from werkzeug.exceptions import Forbidden, BadRequest

from task_run import TaskRunAPI
from pybossa.util import get_user_id_or_ip
from pybossa.core import user_repo, task_repo, sentinel


class CompletedTaskRunAPI(TaskRunAPI):

    """Class API for domain object TaskRun."""

    __class__ = CompletedTaskRun
    reserved_keys = set(['id', 'created', 'finish_time'])
   
    def _forbidden_attributes(self, data):
        for key in data.keys():
            if key in self.reserved_keys:
                raise BadRequest("Reserved keys in payload")
 
    def post(self):
        raise MethodNotAllowed(valid_methods=['GET'])

    def delete(self, oid=None):
        raise MethodNotAllowed(valid_methods=['GET'])

    def put(self, oid=None):
        raise MethodNotAllowed(valid_methods=['GET'])

    def is_admin_api_key(self):
        """Check if api_key passed is of admin_user"""
        if 'api_key' in request.args.keys():
            apikey = request.args['api_key']
            user = user_repo.get_by(api_key=apikey)
            if user:
                return user.admin
        return False

    def _custom_filter(self, filters):
        # authorize admin api_key to perform this operation
        if self.is_admin_api_key():
            return filters
        raise BadRequest("Insufficient privilege to the request")

    def _filter_query(self, repo_info, limit, offset):
        filters = {}
        for k in request.args.keys():
            if k not in ['limit', 'offset', 'api_key', 'exported']:
                # Raise an error if the k arg is not a column
                getattr(self.__class__, k)
            
            # if exported col is part of k, add it to the filter
            # as it is part of Task table and will be explicitly
            # searched in Task table later
            if k not in ['limit', 'offset', 'api_key']:
                filters[k] = request.args[k]
        repo = repo_info['repo']
        query_func = repo_info['filter']
        filters = self._custom_filter(filters)
        results = getattr(repo, query_func)(limit=limit, offset=offset, **filters)
        return results


