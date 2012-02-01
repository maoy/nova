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

import functools
import logging

from nova.db import api as dbapi
from nova import flags
from nova import utils
from nova.openstack.common import cfg
from nova import exception

LOG = logging.getLogger(__name__)

FLAGS = flags.FLAGS

import common
import task


class TaskAPI(common.TaskAPI):
    """Task API implementation backed by a SQL database"""

    @classmethod
    def create_task(cls, context, prio, info=None):
        assert context.task_id is None, \
            "context already has a task id %s" % (context.task_id)
        task_ref = dbapi.task_create(context,
            {'state': common.TaskState.RUNNING,
             'info': info,
             'prio': prio,
             'depth': 0,
             'context': utils.dumps(context.to_dict()),
             'execlog': "[]"})
        context.task_id = task_ref['id']
        LOG.info("task %d created", context.task_id)
        return task_ref

    @classmethod
    def get_task(cls, context):
        if context is None:
            raise ValueError("context is None")
        if context.task_id is None:
            return None
        return dbapi.task_get(context, context.task_id)

    @classmethod
    def update_task(cls, context, data):
        assert context.task_id is not None, \
            "no task_id in the context while updating task to %r" % data
        return dbapi.task_update(context, context.task_id, data)

    @classmethod
    def append_task_log(cls, context, record):
        """
        append the record to execlog, and update depth
        
        This is slightly more efficient than the default implementation.
        """
        assert context.task_id is not None, \
            "no task_id in the context while append task log %r" % record
        depth = record["depth"]
        return dbapi.task_update(context, context.task_id,
                                 {"depth": depth, "_appendlog": record})

    @classmethod
    def exit_task(cls, context):
        """Terminate the task in the context"""
        LOG.debug(_("exiting task %d"), context.task_id)
        tid = context.task_id
        dbapi.lock_delete_all(context, tid)
        try:
            dbapi.task_update(context, tid,
                              {"state": common.TaskState.TERMINATED})
        except Exception:
            # Note(maoy):
            # we ignore the exception here in the same spirit as
            # those closeQuietly calls to avoid exceptions compounding.
            LOG.exception("in exit_task, ignore")
        LOG.info("task %d terminated", context.task_id)
        context.task_id = None

    @classmethod
    def acquire_lock(cls, context, resource,
                     style=common.LockStyle.Exclusive):
        """
        """
        assert context.task_id is not None, "no task_id in the context"
        tid = context.task_id
        dbapi.lock_create(context, {'name': resource,
                           'tid': tid,
                           'style': style,
                           })
        LOG.debug(_("acquired locks for %s on %s"), tid, resource)
