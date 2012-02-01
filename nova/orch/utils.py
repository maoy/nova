# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 AT&T.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# helper methods

import functools
import logging

from nova import flags
from nova import utils

from nova.orch import common
from nova.orch import task

LOG = logging.getLogger(__name__)

FLAGS = flags.FLAGS


def _begin_task_call(context, name, args=None, kwargs=None, host=None):
    task_ref = task.api.get_task(context)
    if task_ref is None:
        task_ref = task.api.create_task(context, 0)
    assert task_ref["state"] != common.TaskState.TERMINATED, \
        "task already terminated when begin a call"
    depth = task_ref["depth"] + 1
    # to begin a call, write a new log record
    logrecord = {"depth": depth,
                 "host": host,
                 "type": "begin",
                 "args": args,
                 "kwargs": kwargs,
                 "name": name,
                 "ts": utils.strtime()}
    LOG.info("begin task call: %s", logrecord)
    task.api.append_task_log(context, logrecord)  # will update depth too


def _end_task_call(context, name, retval, error=None, host=None):
    """The call either ended successfully with a return value or an exception
    """
    task_ref = task.api.get_task(context)
    assert task_ref is not None, "not found task when trying end a call"
    assert task_ref["state"] != common.TaskState.TERMINATED, \
        "task already terminated when end a call"
    # TODO(maoy): check if end match with begin in log
    depth = task_ref["depth"] - 1
    assert depth >= 0, "depth <0"
    # to end a call, write a new log record
    logrecord = {"depth": depth,
                 "host": host,
                 "type": "end",
                 "retval": retval,
                 "name": name,
                 "ts": utils.strtime(),
                 "error": None if error is None else repr(error)}

    LOG.info("end task call: %s", logrecord)
    task.api.append_task_log(context, logrecord)  # will update depth too
    if depth == 0:
        task.api.exit_task(context)


def task_method(function):
    """a decorator for a class method to automatically use begin
    and end task_call"""
    @functools.wraps(function)
    def decorated_function(self, context, *args, **kwargs):
        if context is None:
            LOG.warning("context is None. Disable orchestration. \
 Are we in testing?")
            return function(self, context, *args, **kwargs)
        host = "%s.%s" % (self.service_name, self.host)
        funcname = "%s.%s" % (self.__class__.__name__, function.__name__)
        _begin_task_call(context, funcname, args, kwargs, host=host)
        try:
            retval = function(self, context, *args, **kwargs)
        except Exception, exc:
            _end_task_call(context, funcname, None, error=exc, host=host)
            raise
        # no exception
        _end_task_call(context, funcname, retval, host=host)
        return retval

    if FLAGS.orch_enabled:
        return decorated_function
    #fall back to no orchestration
    return function
