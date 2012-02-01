# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 AT&T
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from nova import context
from nova import exception
from nova import flags
from nova import log as logging
from nova.openstack.common import importutils

from nova import rpc
from nova import test

#from nova.orch import task
from nova.orch.task import api as taskapi
from nova.orch import utils as orch_utils

LOG = logging.getLogger(__name__)


class TaskTestCase(test.TestCase):

    def setUp(self):
        super(TaskTestCase, self).setUp()

    def tearDown(self):
        super(TaskTestCase, self).tearDown()

    def test_create_tasks(self):
        context1 = context.RequestContext('testuser', 'testproject',
                                          is_admin=False)
        context2 = context.RequestContext('testuser', 'testproject',
                                          is_admin=False)
        taskapi.create_task(context1, 0)
        taskapi.create_task(context2, 0)
        self.assert_(context1.task_id != context2.task_id)
        taskapi.update_task(context1, {"info":"update"})
        taskapi.exit_task(context1)
        taskapi.exit_task(context2)

    def test_task_calls(self):
        context1 = context.RequestContext('testuser', 'testproject',
                                          is_admin=False)
        context2 = context.RequestContext('testuser', 'testproject',
                                          is_admin=False)

        class Dummy(object):

            service_name = "dummy"
            host = "fake"

            @orch_utils.task_method
            def call1(self, context, foo, bar="stuff"):
                LOG.info("in call1, foo=%s, bar=%s", foo, bar)
                return self.call2(context, foo)

            @orch_utils.task_method
            def call2(self, context, foo):
                LOG.info("in call2, foo=%s", foo)
                if foo == "alice":
                    return 101
                raise RuntimeError("we made this up")

        dummy = Dummy()
        self.assert_(dummy.call1(context1, "alice") == 101)
        self.assertRaises(RuntimeError, dummy.call1, context2, "bob")
