from marshmallow import Schema, fields

from typing import Optional, List, Any, Dict

from golem.envs.docker import DockerBind


class CloudConfigSchemaBind(Schema):
    source = fields.Str()
    target = fields.Str()
    mode = fields.Str()


class CloudConfigSchemaNetworkingEndpoint(Schema):
    aliases = fields.List(fields.Str())
    links = fields.Dict(keys=fields.Str(), values=fields.Str())
    ipv4_address = fields.Str()
    ipv6_address = fields.Str()
    link_local_ips = fields.List(fields.Str())


class CloudConfigSchemaContainer(Schema):
    image = fields.Str(required=True)
    tag = fields.Str(required=True, default='latest')
    command: Optional[str] = fields.Str()
    ports: Optional[List[int]] = fields.List(fields.Int())
    env: Optional[Dict[str, str]] = fields.Dict(keys=fields.Str(),
                                                values=fields.Str())
    work_dir: Optional[str] = fields.Str()
    binds: Optional[List[DockerBind]] = None
    networking_config: Optional[Dict[str, Any]] = fields.Dict(
        keys=fields.Str(),
        values=fields.Nested(CloudConfigSchemaNetworkingEndpoint))
    hostname: Optional[str] = fields.Str()
    domainname: Optional[str] = fields.Str()
    healthcheck: Optional[Dict[str, Any]] = fields.Dict(
        keys=fields.Str(),
        values=fields.Str())
    extra_hosts: Optional[Dict[str, str]] = fields.Dict(keys=fields.Str(),
                                                        values=fields.Str())
    links: Optional[Dict[str, Optional[str]]] = fields.Dict(
        keys=fields.Str(),
        values=fields.Str())
    mem_reservation: Optional[int] = fields.Int()
    restart_policy: Optional[Dict[str, Any]] = fields.Dict(
        keys=fields.Str(),
        values=fields.Str())


class CloudConfigSchemaDeployment(Schema):
    name = fields.Str(required=True)
    container = fields.Nested(CloudConfigSchemaContainer, required=True)


class CloudConfigSchema(Schema):
    containers = fields.List(fields.Nested(CloudConfigSchemaDeployment))
