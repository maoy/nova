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

from nova import exception


class TaskState(object):
    """Enum for task state"""
    RUNNING = "Running"
    BLOCKED = "Blocked"
    TERMINATED = "Terminated"


class LockStyle(object):
    """constants for lock style"""
    Exclusive = 1
    Shared = 0


class TaskAPI(object):
    """Nova orchestration API abstraction."""

    def __new__(cls):
        raise TypeError("API class should not be instantiated.")

    @classmethod
    def create_task(cls, context, prio, info=None):
        """Create task data structure, put the task_id in context.
        prio is the priority of the task.
        """
        raise NotImplementedError()

    @classmethod
    def get_task(context):
        """Get task from the current context. If it doesn't exist,
        return None.
        The return value is a dict-like data structure with the
        following fields:
          id: task_id
          state: of type TaskState
          prio: task priority
          depth: the current call stack depth
          context: RequestContext
          info: task specific opaque state
          execlog: execution logs as a list of log records.
            each record is a dict of
              depth: the stack depth at the time of the call
              host: where the call is issued: e.g. compute.host1
              name: call method name
              ts: log timestamp
              type: "begin" before a call or "end" after a call.
              If type=="begin":
              args: positional arguments
              kwargs: keyword arguments
              if type=="end":
              retval: function return value if it ends correctly.
              error: the exception when the function ends.
        """
        raise NotImplementedError()

    @classmethod
    def update_task(cls, context, data):
        """Update the task data structure. data is a dict or alike.
        valid keys are "prio" and "info"."""
        raise NotImplementedError()

    @classmethod
    def exit_task(cls, context):
        """End a task normally. Release all locks and update
        task state.
        """
        raise NotImplementedError()

    @classmethod
    def kill_task(cls, task_id):
        """Forcefully kill a task and release all locks immediately.
        """
        raise NotImplementedError()

    @classmethod
    def list_tasks(cls, state_filter=None):
        """Return a list of tasks that matches the state_filter.
        If the state_filter is None, all tasks are returned. Otherwise,
        tasks with matching state are returned.
        """
        raise NotImplementedError()

    @classmethod
    def acquire_lock(cls, context, resource, style=LockStyle.Exclusive,
                     timeout=None):
        """Acquire the resource lock. If the lock is held by another
        task, wait until the lock is acquired or timeout."""
        raise NotImplementedError()

    # Note that we do not offer release_lock API for now
    # Locks are automatically released when a task ends or killed.
    # This way we get two-phase locking (2PL) where locks can only
    # grow in the expanding phase or shrink when the task finishes.

    # below are the methods that could be overridden, but has a default
    # implementation based on the above methods

    @classmethod
    def ensure_task(cls, context, prio, info=None):
        """Ensure a task exists in the current context.
        If not, create it.
        Note that prio is only set if the task is not
        present."""
        if context.task_id is not None:
            # context already has a task id
            return cls.update_task(context, {"info": info})
        return cls.create_task(context, prio, info=info)

    @classmethod
    def try_lock(cls, context, resource, style=LockStyle.Exclusive):
        """Try to acquire the resource lock.
        If the lock is being held by another task, immediately stop
        and raise ResourceBusy exception"""
        try:
            cls.acquire_lock(context, resource, style=style, timeout=0)
        except exception.TimeoutError:
            raise exception.ResourceBusy()

    @classmethod
    def append_task_log(cls, context, record):
        """
        append the record to execlog, and update depth
        """
        assert context.task_id is not None, \
            "no task_id in the context while append task log %r" % record
        task_ref = cls.get_task(context)
        depth = record["depth"]
        newlog = task_ref["execlog"] + [record]
        return cls.update_task(context, {"depth": depth, 
                                         "execlog": newlog})
