# -*- coding: utf8 -*-
# This file is part of PyBossa.
#
# Copyright (C) 2013 SF Isle of Man Limited
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
PyBossa api module for exposing domain objects via an API.

This package adds GET, POST, PUT and DELETE methods for:
    * projects,
    * categories,
    * tasks,
    * task_runs,
    * users,
    * global_stats,
    * vmcp
    * completedtasks
    * completedtaskruns

"""

import json
from flask import Blueprint, request, abort, Response, make_response
from flask.ext.login import current_user
from werkzeug.exceptions import NotFound
from pybossa.util import jsonpify, crossdomain, get_user_id_or_ip
import pybossa.model as model
from pybossa.core import csrf, ratelimits, sentinel
from pybossa.ratelimit import ratelimit
from pybossa.cache.projects import n_tasks
import pybossa.sched as sched
from pybossa.error import ErrorStatus
from global_stats import GlobalStatsAPI
from task import TaskAPI
from task_run import TaskRunAPI
from app import AppAPI
from project import ProjectAPI
from category import CategoryAPI
from vmcp import VmcpAPI
from user import UserAPI
from token import TokenAPI
from pybossa.core import project_repo, task_repo
from completed_task import CompletedTaskAPI
from completed_task_run import CompletedTaskRunAPI
from datetime import datetime

blueprint = Blueprint('api', __name__)

cors_headers = ['Content-Type', 'Authorization']

error = ErrorStatus()


@blueprint.route('/')
@crossdomain(origin='*', headers=cors_headers)
@ratelimit(limit=ratelimits.get('LIMIT'), per=ratelimits.get('PER'))
def index():  # pragma: no cover
    """Return dummy text for welcome page."""
    return 'The PyBossa API'


def register_api(view, endpoint, url, pk='id', pk_type='int'):
    """Register API endpoints.

    Registers new end points for the API using classes.

    """
    view_func = view.as_view(endpoint)
    csrf.exempt(view_func)
    blueprint.add_url_rule(url,
                           view_func=view_func,
                           defaults={pk: None},
                           methods=['GET', 'OPTIONS'])
    blueprint.add_url_rule(url,
                           view_func=view_func,
                           methods=['POST', 'OPTIONS'])
    blueprint.add_url_rule('%s/<%s:%s>' % (url, pk_type, pk),
                           view_func=view_func,
                           methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])

register_api(AppAPI, 'api_app', '/app', pk='oid', pk_type='int')
register_api(ProjectAPI, 'api_project', '/project', pk='oid', pk_type='int')
register_api(CategoryAPI, 'api_category', '/category', pk='oid', pk_type='int')
register_api(TaskAPI, 'api_task', '/task', pk='oid', pk_type='int')
register_api(TaskRunAPI, 'api_taskrun', '/taskrun', pk='oid', pk_type='int')
register_api(UserAPI, 'api_user', '/user', pk='oid', pk_type='int')
register_api(GlobalStatsAPI, 'api_globalstats', '/globalstats',
             pk='oid', pk_type='int')
register_api(VmcpAPI, 'api_vmcp', '/vmcp', pk='oid', pk_type='int')
register_api(TokenAPI, 'api_token', '/token', pk='token', pk_type='string')
register_api(CompletedTaskAPI, 'api_completedtask', '/completedtask', pk='oid', pk_type='int')
register_api(CompletedTaskRunAPI, 'api_completedtaskrun', '/completedtaskrun', pk='oid', pk_type='int')

@jsonpify
@blueprint.route('/app/<project_id>/newtask')
@blueprint.route('/project/<project_id>/newtask')
@crossdomain(origin='*', headers=cors_headers)
@ratelimit(limit=ratelimits.get('LIMIT'), per=ratelimits.get('PER'))
def new_task(project_id):
    """Return a new task for a project."""
    # Check if the request has an arg:
    try:
        task = _retrieve_new_task(project_id)
        # If there is a task for the user, return it
        if task is not None:
            mark_task_as_requested_by_user(task, sentinel.master)
            response = make_response(json.dumps(task.dictize()))
            response.mimetype = "application/json"
            return response
        return Response(json.dumps({}), mimetype="application/json")
    except Exception as e:
        return error.format_exception(e, target='project', action='GET')

def _retrieve_new_task(project_id):
    project = project_repo.get(project_id)
    if project is None:
        raise NotFound
    if not project.allow_anonymous_contributors and current_user.is_anonymous():
        info = dict(
            error="This project does not allow anonymous contributors")
        error = model.task.Task(info=info)
        return error
    if request.args.get('offset'):
        offset = int(request.args.get('offset'))
    else:
        offset = 0
    user_id = None if current_user.is_anonymous() else current_user.id
    user_ip = request.remote_addr if current_user.is_anonymous() else None
    task = sched.new_task(project_id, project.info.get('sched'), user_id, user_ip, offset)
    return task

def mark_task_as_requested_by_user(task, redis_conn):
    usr = get_user_id_or_ip()['user_id'] or get_user_id_or_ip()['user_ip']
    key = 'pybossa:task_requested:user:%s:task:%s' % (usr, task.id)
    timeout = 60 * 60
    redis_conn.setex(key, timeout, True)


@jsonpify
@blueprint.route('/app/<task_id>/cachePresentedTime')
@blueprint.route('/task/<task_id>/cachePresentedTime')
@crossdomain(origin='*', headers=cors_headers)
@ratelimit(limit=ratelimits.get('LIMIT'), per=ratelimits.get('PER'))
def cache_presented_time(task_id):
    # 'force' set to False since we do not want to overwrite
    # the presented time on browser reloads or accidental logouts.
    set_cache_presented_time(task_id, force=False)
    return Response(json.dumps({}), mimetype="application/json")

def set_cache_presented_time(task_id, force=False):
    """Cache in Redis the initial datetime that a task was presented to a user.

    If force=True, cache will be updated if there is no key or an existing key.
    If force=False, cache will only be updated if no key exists.
    """
    # usr can only be a registered user with a user_id
    usr = get_user_id_or_ip()['user_id'] or None
    redis_conn = sentinel.master

    # Timeout set for 60 minutes to coincide with inactivity timeout
    timeout = 60 * 60

    # Only set cache if usr is not None so that the cache cannot be set
    # by calling the API directly
    if redis_conn is not None and usr is not None:
        presented_time = datetime.utcnow().isoformat()
        presented_time_key = 'pybossa:user:{0}:task_id:{1}:presented_time_key'.format(usr, task_id)

        # Set presented_time value if presented_time_key does not exist yet.
        # The presented time cannot be reset until it times out. 
        # This will eliminate the ability for someone to manipulate the presented time
        # to make it look like they spent less time on a task than they actually did.
        # Besides user manipulation, if guards against browser reloads and accidental logouts.
        # This is an appropriate solution since we do not have complete information
        # regarding whether or not a user actually looked at a task before a browser reload,
        # logout or timeout.
        if redis_conn.get(presented_time_key) is None:
            redis_conn.setex(presented_time_key, timeout, presented_time)
        # Only overwrite an existing presented_time_value if force = True.
        # This should ONLY be used if there is no way for a user to take advantage
        # of this feature to manuipulate the presented time.
        elif force == True:
            redis_conn.setex(presented_time_key, timeout, presented_time)


@jsonpify
@blueprint.route('/app/<short_name>/userprogress')
@blueprint.route('/project/<short_name>/userprogress')
@blueprint.route('/app/<int:project_id>/userprogress')
@blueprint.route('/project/<int:project_id>/userprogress')
@crossdomain(origin='*', headers=cors_headers)
@ratelimit(limit=ratelimits.get('LIMIT'), per=ratelimits.get('PER'))
def user_progress(project_id=None, short_name=None):
    """API endpoint for user progress.

    Return a JSON object with two fields regarding the tasks for the user:
        { 'done': 10,
          'total: 100
        }
       This will mean that the user has done a 10% of the available tasks for
       him

    """
    if project_id or short_name:
        if short_name:
            project = project_repo.get_by_shortname(short_name)
        elif project_id:
            project = project_repo.get(project_id)

        if project:
            # For now, keep this version, but wait until redis cache is used here for task_runs too
            query_attrs = dict(project_id=project.id)
            if current_user.is_anonymous():
                query_attrs['user_ip'] = request.remote_addr or '127.0.0.1'
            else:
                query_attrs['user_id'] = current_user.id
            taskrun_count = task_repo.count_task_runs_with(**query_attrs)
            tmp = dict(done=taskrun_count, total=n_tasks(project.id))
            return Response(json.dumps(tmp), mimetype="application/json")
        else:
            return abort(404)
    else:  # pragma: no cover
        return abort(404)
