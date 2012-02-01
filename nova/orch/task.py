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

"""
Orchestration service for transactional task management.
"""
import logging

from nova import flags
from nova.openstack.common import cfg
from nova.openstack.common import importutils


LOG = logging.getLogger(__name__)

orchestration_opts = [
    cfg.BoolOpt('orch_enabled',
               default=True,
               help='enable orchestration feature'),
    cfg.StrOpt('orch_backend',
               default='nova.orch.localmem_impl',
               help='The backend to use for orchstration'),
                      ]

FLAGS = flags.FLAGS
FLAGS.register_opts(orchestration_opts)


def _get_impl():
    """Delay import of orchstration backend until configuration is loaded."""
    global api
    if isinstance(api, LazyLoadClass):
        api_module = importutils.import_module(FLAGS.orch_backend)
        api = getattr(api_module, "TaskAPI")
    return api


class LazyLoadClass(object):
    """
    Lazy load the TaskAPI class from the backend.

    All methods are stateless classmethods.
    """
    def __getattr__(self, name):
        print "*******name", name
        obj = getattr(_get_impl(), name)
        setattr(self, name, obj)  # cache it
        return obj


api = LazyLoadClass()
