from venom import Message
from venom.fields import Field, repeated, String, Map, Bool, MapField, Repeat
from venom.rpc import Stub
from venom.rpc import http


class SchemaMessage(Message):
    type: str  # TODO: enum
    description: str
    properties = MapField('venom.rpc.reflect.openapi.SchemaMessage')
    ref = String(json_name='$ref')
    additional_properties = Field('venom.rpc.reflect.openapi.SchemaMessage')
    items = Field('venom.rpc.reflect.openapi.SchemaMessage')


class ParameterMessage(Message):
    is_in = String(json_name='in')  # TODO: enum
    description: str
    required: bool
    name: str
    type: str
    items: SchemaMessage
    schema: SchemaMessage


class ResponseMessage(Message):
    description: str
    schema: SchemaMessage


class ResponsesMessage(Message):
    default: ResponseMessage  # TODO: error codes


class OperationMessage(Message):
    produces: Repeat[str]
    responses: ResponsesMessage
    parameters: Repeat[ParameterMessage]


class InfoMessage(Message):
    version: str
    title: str
    description: str
    terms_of_service: str
    contact: str
    license: str


class PathsMessage(Message):
    get: OperationMessage
    put: OperationMessage
    post: OperationMessage
    delete: OperationMessage
    options: OperationMessage
    head: OperationMessage
    patch: OperationMessage


class OpenAPISchema(Message):
    swagger: str
    schemes: Repeat[str]
    consumes: Repeat[str]
    produces: Repeat[str]
    info: InfoMessage
    host: str
    base_path: str
    paths: Map[str, PathsMessage]
    definitions: Map[str, SchemaMessage]


class ReflectStub(Stub):
    @http.GET('/openapi.json')
    def get_openapi_schema(self) -> OpenAPISchema:
        raise NotImplementedError()
