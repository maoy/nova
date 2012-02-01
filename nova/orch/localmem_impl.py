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
from nova.orch import common
from nova.orch import task


LOG = logging.getLogger(__name__)

FLAGS = flags.FLAGS


class TaskAPI(common.TaskAPI):
    """Task API implementation backed by local memory.
    All tasks should be local, and the threads are
    green from eventlet."""

    _tasks = {}  # task_id -> task
    _locks = {}  # resource_id -> (task_id, style)
    _lock_idx = {}  # task_id -> set of resource_id
    _counter = 0

    @classmethod
    def _get_new_task_id(cls):
        # We assume eventlet thread model here
        # So no need to lock/unlock
        cls._counter += 1
        return cls._counter

    @classmethod
    def create_task(cls, context, prio, info=None):
        assert context.task_id is None, \
            "context already has a task id %s" % (context.task_id)
        task_id = cls._get_new_task_id()
        task_ref = \
            {'id': task_id,
             'state': common.TaskState.RUNNING,
             'info': info,
             'prio': prio,
             'depth': 0,
             'context': utils.dumps(context.to_dict()),
             'execlog': []}
        context.task_id = task_ref['id']
        cls._tasks[task_id] = task_ref
        LOG.info("task %d created", context.task_id)
        # Note: we are returning the mutable version here
        # so that task_ref can be modified outside of the APIs
        # with side effect, which is frowned upon.
        return task_ref

    @classmethod
    def get_task(cls, context):
        if context is None:
            raise ValueError("context is None")
        if context.task_id is None:
            return None
        return cls._tasks[context.task_id]

    @classmethod
    def update_task(cls, context, data):
        assert context.task_id is not None, \
            "no task_id in the context while updating task to %r" % data
        cls._tasks[context.task_id].update(data)

    @classmethod
    def exit_task(cls, context):
        """Terminate the task in the context"""
        LOG.debug(_("exiting task %d"), context.task_id)
        tid = context.task_id
        cls._lock_delete_all(tid)
        try:
            task_ref = cls._tasks[tid]
            task_ref["state"] = common.TaskState.TERMINATED
        except Exception:
            # Note(maoy):
            # we ignore the exception here in the same spirit as
            # those closeQuietly calls to avoid exceptions compounding.
            LOG.exception("in exit_task, ignore")
        LOG.info("task %d terminated", context.task_id)
        context.task_id = None

    @classmethod
    def _lock_delete_all(cls, tid):
        lockset = cls._lock_idx.get(tid, set())
        for rid in lockset:
            cls._locks.pop(rid, None)
        cls._lock_idx.pop(tid, None)

    @classmethod
    def acquire_lock(cls, context, resource,
                     style=common.LockStyle.Exclusive):
        assert context.task_id is not None, "no task_id in the context"
        if resource is None:  # acquire lock on None is a no-op
            return
        tid = context.task_id
        if resource in cls._locks:
            ltid, _style = cls._locks[resource]
            if ltid != tid:  # lock held by others
                LOG.info(_("task %s: lock on %s is held by %s"),
                          tid, resource, ltid)
                raise exception.ResourceBusy
            else:  # we already own the lock
                return
        cls._locks[resource] = (tid, style)
        lockset = cls._lock_idx.get(tid, set())
        cls._lock_idx[tid] = lockset.union(set([resource]))
        LOG.debug(_("acquired locks for %s on %s"), tid, resource)

    @classmethod
    def recycle_tasks(cls):
        """Remove all the tasks that are terminated."""
        for tid in cls._tasks:
            if cls._tasks[tid]["state"] == common.TaskState.TERMINATED:
                del cls._tasks[tid]
