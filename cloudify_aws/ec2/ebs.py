########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

# Built in Imports
import datetime

# Third-party Imports
from boto import exception

# Cloudify imports
from cloudify_aws import utils, constants
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation
from cloudify_aws.base import AwsBaseNode, AwsBaseRelationship


@operation
def creation_validation(**_):
    return Ebs().creation_validation()


@operation
def create(args, **_):
    return Ebs().created(args)


@operation
def delete(args=None, **_):
    return Ebs().deleted(args)


@operation
def start(args=None, **_):
    return Ebs().started(args)


@operation
def create_snapshot(args, **_):
    return Ebs().snapshot_created(args)


@operation
def associate(args=None, **_):
    return VolumeInstanceConnection().associated(args)


@operation
def disassociate(args, **_):
    return VolumeInstanceConnection().disassociated(args)


class VolumeInstanceConnection(AwsBaseRelationship):

    def __init__(self, client=None):
        super(VolumeInstanceConnection, self).__init__(client=client)
        self.not_found_error = constants.EBS['NOT_FOUND_ERROR']
        self.resource_id = None
        self.source_get_all_handler = {
            'function': self.client.get_all_volumes,
            'argument':
                '{0}_ids'.format(constants.EBS['AWS_RESOURCE_TYPE'])
        }

    def associate(self, args=None, **_):

        volume_id = \
            utils.get_external_resource_id_or_raise(
                'attach volume', ctx.source.instance)
        instance_id = \
            utils.get_external_resource_id_or_raise(
                'attach volume', ctx.target.instance)

        if ctx.source.node.properties[constants.ZONE] not in \
                ctx.target.instance.runtime_properties.get('placement'):
            ctx.logger.info(
                'Volume Zone {0} and Instance Zone {1} do not match. '
                'This may lead to an error.'.format(
                    ctx.source.node.properties[constants.ZONE],
                    ctx.target.instance.runtime_properties
                    .get('placement')
                )
            )

        volume_object = self.get_source_resource()

        if not volume_object:
            raise NonRecoverableError(
                'EBS volume {0} not found in account.'.format(volume_id))

        if constants.EBS['VOLUME_CREATING'] in volume_object.update():
            return False
        elif constants.EBS['VOLUME_AVAILABLE'] not in volume_object.update():
            raise NonRecoverableError(
                'Cannot attach Volume {0} because it is in state {1}.'
                .format(volume_object.id, volume_object.status))

        associate_args = dict(
            volume_id=volume_id,
            instance_id=instance_id,
            device=ctx.source.node.properties['device']
        )
        associate_args = utils.update_args(associate_args, args)

        return self.execute(self.client.attach_volume, associate_args,
                            raise_on_falsy=True)

    def associated(self, args=None):

        ctx.logger.info(
            'Attempting to associate {0} with {1}.'
            .format(self.source_resource_id,
                    self.target_resource_id))

        if self.use_source_external_resource_naively() \
                or self.associate(args):
            return self.post_associate()

        return ctx.operation.retry(
            message='Failed to associate {0} with {1}.'
                    .format(self.source_resource_id,
                            self.target_resource_id))

    def disassociate(self, args=None, **_):

        """ Detaches an EBS Volume created by Cloudify from an EC2 Instance
        that was also created by Cloudify.
        """

        volume_id = self.source_resource_id
        instance_id = self.target_resource_id

        volume_object = self.get_source_resource()

        if not volume_object:
            raise NonRecoverableError(
                'EBS volume {0} not found in account.'.format(volume_id))

        disassociate_args = dict(
            volume_id=volume_id,
            instance_id=instance_id,
            device=ctx.source.node.properties['device']
        )

        disassociate_args = utils.update_args(disassociate_args, args)

        return self.execute(self.client.detach_volume, disassociate_args,
                            raise_on_falsy=True)

    def post_associate(self):

        super(VolumeInstanceConnection, self).post_associate()
        ctx.source.instance.runtime_properties['instance_id'] = \
            self.target_resource_id

        return True

    def post_disassociate(self):

        super(VolumeInstanceConnection, self).post_disassociate()
        utils.unassign_runtime_property_from_resource(
            'instance_id', ctx.source.instance)

        return True


class Ebs(AwsBaseNode):

    def __init__(self):
        super(Ebs, self).__init__(
            constants.EBS['AWS_RESOURCE_TYPE'],
            constants.EBS['REQUIRED_PROPERTIES']
        )
        self.not_found_error = constants.EBS['NOT_FOUND_ERROR']
        self.get_all_handler = {
            'function': self.client.get_all_volumes,
            'argument': '{0}_ids'.format(constants.EBS['AWS_RESOURCE_TYPE'])
        }

    def create(self, args=None, **_):
        """Creates an EBS volume.
        """

        create_volume_args = dict(
            size=ctx.node.properties['size'],
            zone=ctx.node.properties[constants.ZONE]
        )
        create_volume_args = utils.update_args(create_volume_args, args)

        new_volume = self.execute(self.client.create_volume,
                                  create_volume_args, raise_on_falsy=True)
        ctx.instance.runtime_properties[constants.ZONE] = new_volume.zone

        self.resource_id = new_volume.id

        return True

    def start(self, args=None, **_):
        return True

    def delete(self, args=None, **_):
        """ Deletes an EBS Volume.
        """

        if not self._delete_volume(args):
            return False

        utils.unassign_runtime_property_from_resource(
            constants.ZONE, ctx.instance)

        return True

    def deleted(self, args=None):

        ctx.logger.info(
            'Attempting to delete {0} {1}.'
            .format(self.aws_resource_type,
                    self.cloudify_node_instance_id))

        if not self.get_resource():
            self.raise_forbidden_external_resource(self.resource_id)

        if self.delete_external_resource_naively() or self.delete(args):
            return self.post_delete()
        elif not self.delete(args):
            return ctx.operation.retry(
                message='Failed to delete volume {0}.'
                .format(self.resource_id))
        else:
            raise NonRecoverableError(
                'Neither external resource, nor Cloudify resource, '
                'unable to delete this resource.')

    def _delete_volume(self, args):
        """

        :return: True if the item is deleted,
        False if the item cannot be deleted yet.
        """

        volume_to_delete = self.get_resource()

        if not volume_to_delete:
            ctx.logger.info(
                'Volume id {0} does not exist.'
                .format(self.resource_id))
            return True

        if volume_to_delete.status not in constants.EBS['VOLUME_AVAILABLE'] \
                or volume_to_delete.status in constants.EBS['VOLUME_IN_USE']:
            return False

        delete_args = dict(volume_id=self.resource_id)
        delete_args = utils.update_args(delete_args, args)
        return self.execute(self.client.delete_volume,
                            delete_args, raise_on_falsy=True)

    def create_snapshot(self, args=None, **_):
        """ Create a snapshot of an EBS Volume
        """

        volume_id = \
            utils.get_external_resource_id_or_raise(
                'create snapshot', ctx.instance)

        ctx.logger.info(
            'Trying to create a snapshot of EBS volume {0}.'
            .format(volume_id))

        snapshot_desc = \
            unicode(datetime.datetime.now()) + \
            ctx.instance.runtime_properties[constants.EXTERNAL_RESOURCE_ID]
        create_args = dict(volume_id=volume_id, description=snapshot_desc)
        create_args = utils.update_args(create_args, args)

        try:
            new_snapshot = self.execute(self.client.create_snapshot,
                                        create_args, raise_on_falsy=True)
        except (exception.EC2ResponseError,
                exception.BotoServerError) as e:
            raise NonRecoverableError('{0}'.format(str(e)))

        if constants.EBS['VOLUME_SNAPSHOT_ATTRIBUTE'] not in \
                ctx.instance.runtime_properties:
            ctx.instance.runtime_properties[
                constants.EBS['VOLUME_SNAPSHOT_ATTRIBUTE']] = list()

        ctx.instance.runtime_properties[
            constants.EBS['VOLUME_SNAPSHOT_ATTRIBUTE']].append(new_snapshot.id)

        return True

    def snapshot_created(self, args=None):
        ctx.logger.info(
            'Attempting to create snapshot of EBS volume {0}.'
            .format(self.resource_id))

        if self.create_snapshot(args):
            return self.post_snapshot_create()

    def post_snapshot_create(self):
        ctx.logger.info(
            'Created snapshot of EBS volume {0}.'
            .format(self.resource_id))
