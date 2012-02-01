"""
temporary hacks and notes for transactional task management
"""
import functools
import json
import logging

from nova.db import api as dbapi
from nova import flags
from nova import utils
from nova.openstack.common import cfg
from nova import exception

LOG = logging.getLogger(__name__)

orchestration_opts = [
    cfg.BoolOpt('orch_enabled',
               default=True,
               help='enable orchestration feature'),
                      ]

FLAGS = flags.FLAGS
FLAGS.register_opts(orchestration_opts)


class TaskState(object):
    """Enum for task state"""
    RUNNING = "Running"
    BLOCKED = "Blocked"
    TERMINATED = "Terminated"

class LockStyle(object):
    """constants for lock style"""
    Exclusive = 1
    Shared = 0

# client-side orchestration APIs

def create_task(context, info=None):
    """Create task in db, generate task_id, put in context
    """
    assert context.task_id is None, "context already has a task id %s" % (context.task_id)
    task_ref = dbapi.task_create(context, 
        {'state':TaskState.RUNNING, 'info':info,
         'depth':0,
         'context': utils.dumps(context.to_dict()),
         'execlog':"[]"})
    context.task_id = task_ref['id']
    LOG.info("task %d created", context.task_id) 
    return task_ref

def ensure_task(context, info=None):
    """ensure a task exists in the current context
    """
    if context.task_id is not None:
        # context already has a task id
        return update_task_info(context, info)
    return create_task(context, info=info)

def get_task(context):
    if context.task_id is None:
        return None
    return dbapi.task_get(context, context.task_id)

def update_task_info(context, info):
    assert context.task_id is not None, "no task_id in the context while updating task_info to %r" % info
    return dbapi.task_update(context, context.task_id, {"info": info})

def append_task_log(context, record):
    """
    append the record to execlog, and update depth
    """
    assert context.task_id is not None, "no task_id in the context while append task log %r" % record
    depth = record["depth"]
    return dbapi.task_update(context, context.task_id, 
                             {"depth": depth, "_appendlog": record})
    
    
def terminate_task(context):
    """Terminate the task in the context"""
    LOG.debug(_("terminating task %d"), context.task_id)
    tid = context.task_id
    dbapi.lock_delete_all(context, tid)
    try:
        dbapi.task_update(context, tid, {"state": TaskState.TERMINATED})
    except Exception:
        LOG.exception("in terminate_task, ignore")
    LOG.info("task %d terminated", context.task_id) 
    context.task_id = None


def acquire_lock(context, resource, style=LockStyle.Exclusive):
    """
    """
    assert context.task_id is not None, "no task_id in the context"
    tid = context.task_id
    dbapi.lock_create(context, {'name': resource,
                       'tid': tid,
                       'style': style,
                       })
    LOG.debug(_("acquired locks for %s on %s"), tid, resource)

def release_all_locks(context):
    dbapi.lock_delete_all(context, context.task_id)


def begin_task_call(context, name, args=None, kwargs=None, host=None):
    task_ref = get_task(context)
    if task_ref is None:
        task_ref = create_task(context)
    assert task_ref["state"] != TaskState.TERMINATED, "task already terminated when begin a call"
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
    append_task_log(context, logrecord) # will update depth too

def end_task_call(context, name, retval, error=None, host=None):
    """
    the call either ended successfully with a return value or an exception
    """
    task_ref = get_task(context)
    assert task_ref is not None, "not found task when trying end a call"
    assert task_ref["state"] != TaskState.TERMINATED, "task already terminated when end a call"
    # TODO: check if end match with begin in log
    depth = task_ref["depth"] -1
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
    
    append_task_log(context, logrecord) # will update depth too
    if depth == 0:
        terminate_task(context)
    
def dec_task_method(function):
    """a decorator for a class method to automatically use begin and end task_call"""
    @functools.wraps(function)
    def decorated_function(self, context, *args, **kwargs):
        host = "%s.%s" % (self.service_name, self.host)
        funcname = "%s.%s" % (self.__class__.__name__, function.__name__)
        begin_task_call(context, funcname, args, kwargs, host=host)
        try:
            retval = function(self, context, *args, **kwargs)
        except Exception, exc:
            end_task_call(context, funcname, None, error=exc, host=host)
            raise
        # no exception
        end_task_call(context, funcname, retval, host=host)
        return retval
    
    if FLAGS.orch_enabled:
        return decorated_function
    #fall back to no orchestration
    return function

##### deprecated stuff #####
#class Task(object):
#    def __init__(self, task_id=-1, context=None):
#        self.task_id = task_id
#        self.context = context
#        self.last_updated = utils.utcnow()
#        self.state = TaskState.INIT
#        self.info = "task specific"
#        self.shared_locks = set() #e.g. ["instance-deadbeef", "volume-1234"]
#        self.exclusive_locks = set()
#        self.execution_log = []
#        
#class TaskManager(object):
#    """Dummy implementation in memory task manager"""
#
#    def __init__(self):
#        self._last_task_id = 0
#        self._task_db = {}
#        self._exclusive_locks = {}
#        self._shared_locks = {}
#    
#    def _generate_task_id(self):
#        self._last_task_id += 1
#        return self._last_task_id
#
#    def create_task(self, context):
#        task_id = self._generate_task_id()
#        t = Task(task_id=task_id, context=context)
#        self._task_db[task_id] = t
#        LOG.debug(_("create task with id=%s"), task_id)
#        return task_id
#    
#    def get_task(self, tid):
#        return self._task_db[tid]
#    
#    # APIs to change task data structures:
#    def send_signal(self, task_id, signal):
#        pass
#    
#    def acquire_locks(self, tid, resources, type_):
#        """
#        we ignore type_ for now. only deal with exclusive locks
#        """
#        assert tid in self._task_db
#        for obj in resources:
#            if obj in self._exclusive_locks:
#                raise exception.ResourceBusy( \
#                  busy_resource=(obj, self._exclusive_locks[obj]))
#        for obj in resources:
#            self._exclusive_locks[obj] = tid
#        LOG.debug(_("acquired locks for %s on %s"), tid, resources)
#
#    def release_locks(self, tid, resources):
#        released_objs = []
#        for obj in resources:
#            if obj in self._exclusive_locks:
#                del self._exclusive_locks[obj]
#                released_objs.append(obj)
#                LOG.debug("tid %s released lock on %s", tid, obj)
#            else:
#                LOG.warn("tid %s does not have lock on %s", tid, obj)
#                
#        return released_objs
#    
#    def update_task(self, tid):
#        # execution log, task specific state
#        pass
#    
#    def end_task(self, tid):
#        pass
#
##tm = TaskManager()
