# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import unittest
from cloudify_aws.common.tests.test_base import TestBase, mock_decorator
from cloudify_aws.elb.resources.classic.policy import (ELBClassicPolicy,
                                                       RESOURCE_NAMES,
                                                       RESOURCE_NAME,
                                                       LB_NAME, LB_PORT,
                                                       LISTENER_TYPE)
from cloudify_aws.common.constants import EXTERNAL_RESOURCE_ID
from mock import patch, MagicMock
from cloudify_aws.elb.resources.classic import policy

PATCH_PREFIX = 'cloudify_aws.elb.resources.classic.policy.'


class TestELBClassicPolicy(TestBase):

    def setUp(self):
        super(TestELBClassicPolicy, self).setUp()
        self.policy = ELBClassicPolicy("ctx_node", resource_id=True,
                                       client=MagicMock(), logger=None)
        mock1 = patch('cloudify_aws.common.decorators.aws_resource',
                      mock_decorator)
        mock1.start()
        reload(policy)

    def test_class_properties(self):
        res = self.policy.properties
        self.assertIsNone(res)

    def test_class_status(self):
        res = self.policy.status
        self.assertIsNone(res)

    def test_class_create(self):
        self.policy.client = self.make_client_function(
            'create_load_balancer_policy', return_value='id')
        res = self.policy.create({})
        self.assertEqual(res, 'id')

    def test_class_create_sticky(self):
        self.policy.client = self.make_client_function(
            'create_lb_cookie_stickiness_policy', return_value='id')
        res = self.policy.create_sticky({})
        self.assertEqual(res, 'id')

    def test_class_start(self):
        self.policy.client = self.make_client_function(
            'set_load_balancer_policies_of_listener', return_value='id')
        res = self.policy.start({})
        self.assertEqual(res, 'id')

    def test_class_delete(self):
        self.policy.client = self.make_client_function(
            'delete_load_balancer_policy', return_value='del')
        res = self.policy.delete({})
        self.assertEqual(res, 'del')

    def test_prepare(self):
        ctx = self.get_mock_ctx("ELB")
        policy.prepare(ctx, 'config')
        self.assertEqual(ctx.instance.runtime_properties['resource_config'],
                         'config')

    def test_create(self):
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        ctx_target = self.get_mock_relationship_ctx(
            "elb",
            test_target=self.get_mock_ctx("elb", {},
                                          {EXTERNAL_RESOURCE_ID: 'ext_id'}))
        iface = MagicMock()
        config = {LB_NAME: 'policy'}
        policy.create(ctx, iface, config)
        self.assertTrue(iface.create.called)

        config = {}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = self.mock_return([ctx_target])
            policy.create(ctx, iface, config)
            self.assertTrue(iface.create.called)

    def test_create_sticky(self):
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        ctx_target = self.get_mock_relationship_ctx(
            "elb",
            test_target=self.get_mock_ctx("elb", {},
                                          {EXTERNAL_RESOURCE_ID: 'ext_id'}))
        iface = MagicMock()
        config = {LB_NAME: 'policy'}
        policy.create_sticky(ctx, iface, config)
        self.assertTrue(iface.create_sticky.called)

        config = {}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = self.mock_return([ctx_target])
            policy.create_sticky(ctx, iface, config)
            self.assertTrue(iface.create_sticky.called)

    def test_start_sticky(self):
        def _side(*args):
            if args[1] == LISTENER_TYPE:
                return []
            else:
                return [ctx_target]

        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        ctx_target = self.get_mock_relationship_ctx(
            "elb",
            test_target=self.get_mock_ctx(
                "elb", {},
                {EXTERNAL_RESOURCE_ID: 'ext_id',
                 'resource_config': {'Listeners': [{LB_PORT: 'port'}]}}))
        iface = MagicMock()
        config = {LB_NAME: 'policy', LB_PORT: 'port', RESOURCE_NAMES: 'names'}
        policy.start_sticky(ctx, iface, config)
        self.assertTrue(iface.start.called)

        config = {LB_PORT: 'port', RESOURCE_NAMES: 'names'}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = self.mock_return([ctx_target])
            policy.start_sticky(ctx, iface, config)
            self.assertTrue(iface.start.called)

        config = {RESOURCE_NAMES: 'names'}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = self.mock_return([ctx_target])
            policy.start_sticky(ctx, iface, config)
            self.assertTrue(iface.start.called)

        config = {LB_NAME: 'policy', RESOURCE_NAMES: 'names'}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = MagicMock(side_effect=_side)
            policy.start_sticky(ctx, iface, config)
            self.assertTrue(iface.start.called)

        config = {}
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {},
                                            RESOURCE_NAME: 'name'})
        with patch(PATCH_PREFIX + 'utils') as utils:
            utils.find_rels_by_node_type = self.mock_return([ctx_target])
            policy.start_sticky(ctx, iface, config)
            self.assertTrue(iface.start.called)

    def test_delete(self):
        ctx = self.get_mock_ctx("ELB", {}, {'resource_config': {}})
        iface = MagicMock()
        config = {LB_NAME: 'policy', LB_PORT: 'port', RESOURCE_NAMES: 'names'}
        policy.delete(ctx, iface, config)
        self.assertTrue(iface.delete.called)


if __name__ == '__main__':
    unittest.main()
