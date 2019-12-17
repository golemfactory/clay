from marshmallow import Schema, fields, pre_load, ValidationError

from typing import Optional, List, Any, Dict
from golem.envs.docker import DockerBind


class CloudConfigSchemaNetworkingEndpoint(Schema):
    aliases = fields.List(fields.Str())
    links = fields.Dict(keys=fields.Str(), values=fields.Str())
    ipv4_address = fields.Str()
    ipv6_address = fields.Str()
    link_local_ips = fields.List(fields.Str())


class CloudConfigBindField(fields.Field):
    source = fields.Str()
    target = fields.Str()
    mode = fields.Str()

    def _serialize(self, value, attr, obj, **kwargs):
        source = value.get('source')
        target = value.get('target')
        mode = value.get('mode', ':ro')
        return f'{source}:{target}{mode}'

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None
        if isinstance(value, str):
            parts = value.split(':')
            bind = DockerBind(*parts)
        elif isinstance(value, dict):
            bind = DockerBind(**value)
        elif isinstance(value, DockerBind):
            bind = value
        else:
            raise ValidationError(
                "Bind must be defined either as str or dict.")
        return bind


class CloudConfigSchemaContainer(Schema):
    image = fields.Str(required=True)
    tag = fields.Str(required=True, default='latest')
    command: Optional[str] = fields.Str()
    ports: Optional[List[str]] = fields.List(fields.Str())
    env: Optional[Dict[str, str]] = fields.Dict(keys=fields.Str(),
                                                values=fields.Str())
    work_dir: Optional[str] = fields.Str()
    binds: Optional[List[Any]] = fields.List(CloudConfigBindField())
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
    network_mode: Optional[str] = fields.Str()
    dns: Optional[List[str]] = fields.List(fields.Str())
    dns_search: Optional[List[str]] = fields.List(fields.Str())

    @pre_load
    def process_binds(self, data, **kwargs):
        binds = data.get("binds")
        bind_list = []
        if binds:
            for bind in binds:
                if isinstance(bind, str):
                    bind_parts = bind.split(':')
                    try:
                        bind_mode = bind_parts[2] if len(bind_parts) == 3 \
                            else 'ro'
                    except IndexError:
                        bind_mode = 'ro'
                    bind = {
                        'source': bind_parts[0],
                        'target': bind_parts[1],
                        'mode': bind_mode
                    }
                bind_list.append(bind)
        data["binds"] = bind_list
        return data


class CloudConfigSchemaDeployment(Schema):
    name = fields.Str(required=True)
    container = fields.Nested(CloudConfigSchemaContainer, required=True)


class CloudConfigSchema(Schema):
    containers = fields.List(fields.Nested(CloudConfigSchemaDeployment))
