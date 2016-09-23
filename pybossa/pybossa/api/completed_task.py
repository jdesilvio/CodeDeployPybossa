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
PyBossa api module for exposing domain object Task having completed tasks via an API.

This package adds GET methods for:
    * completedtasks

"""
from werkzeug.exceptions import BadRequest, MethodNotAllowed
from flask import request
from pybossa.model.task import Task
from task import TaskAPI
from pybossa.core import user_repo

class CompletedTaskAPI(TaskAPI):

    """Class for domain object Task."""

    __class__ = Task
    reserved_keys = set(['id', 'created', 'state'])
    
    def _forbidden_attributes(self, data):
        for key in data.keys():
            if key in self.reserved_keys:
                raise BadRequest("Reserved keys in payload")

    def post(self):
        raise MethodNotAllowed(valid_methods=['GET','PUT'])

    def delete(self, oid=None):
        raise MethodNotAllowed(valid_methods=['GET','PUT'])

    def is_admin_api_key(self):
        """Check if api_key passed is of admin_user"""
        if 'api_key' in request.args.keys():
            apikey = request.args['api_key']
            user = user_repo.get_by(api_key=apikey)
            if user:
                return user.admin
        return False

    def _custom_filter(self, filters):
        # authorise admin api_key to perform this operation
        if self.is_admin_api_key():
            # add 'state'='completed' to the filter if missing
            filters['state'] = 'completed'
            return filters
        raise BadRequest("Insufficient privilege to the request")
  

